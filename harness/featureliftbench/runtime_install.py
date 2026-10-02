"""Install pinned DeepSeek Harness and Codex CLIs next to OpenHands.

Binaries land in ``third_party/runtimes/bin`` (gitignored) and are also
symlinked into ``.venv/bin`` when a project venv exists. This is the same
bootstrap model as OpenHands: clone the repo, run ``./setup.sh``, then
``--agent deepseek-harness`` / ``--agent codex`` resolve the CLI without
machine-specific ``agent_bin`` paths.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from .paths import REPO_ROOT
from .runtime_agents import load_runtime_pins
from .runtime_agents import runtime_bin_dir

DSH_NODE_RANGE = "^22.19.0 || >=24.0.0"
_GITHUB_HEADERS = {
    "User-Agent": "FeatureLiftBench-runtime-install",
    "Accept": "application/octet-stream",
}


def default_install_root() -> Path:
    override = os.environ.get("FEATURELIFTBENCH_RUNTIME_ROOT")
    if override:
        return Path(override)
    return REPO_ROOT / "third_party" / "runtimes"


def install_runtime_agents(
    *,
    target: str = "all",
    pins_path: str | Path | None = None,
    dest_root: str | Path | None = None,
    force: bool = False,
) -> dict[str, str]:
    """Install pinned ``dsh`` and/or ``codex`` binaries. Returns dest paths."""

    if target not in {"all", "deepseek-harness", "codex"}:
        raise ValueError(f"unsupported runtime install target: {target}")
    pins = load_runtime_pins(pins_path)
    root = Path(dest_root) if dest_root is not None else default_install_root()
    bin_dir = (
        Path(os.environ["FEATURELIFTBENCH_RUNTIME_BIN_DIR"])
        if os.environ.get("FEATURELIFTBENCH_RUNTIME_BIN_DIR")
        else root / "bin"
    )
    bin_dir.mkdir(parents=True, exist_ok=True)
    installed: dict[str, str] = {}
    errors: list[str] = []
    runtimes = pins["runtimes"]
    if target in {"all", "deepseek-harness"}:
        try:
            installed["deepseek-harness"] = str(
                _install_deepseek_harness(
                    runtimes["deepseek-harness"], root, bin_dir, force=force
                )
            )
        except Exception as exc:
            if target == "deepseek-harness":
                raise
            errors.append(f"deepseek-harness: {exc}")
            print(f"WARNING: {errors[-1]}", file=sys.stderr)
    if target in {"all", "codex"}:
        try:
            installed["codex"] = str(
                _install_codex(runtimes["codex"], root, bin_dir, force=force)
            )
        except Exception as exc:
            if target == "codex":
                raise
            errors.append(f"codex: {exc}")
            print(f"WARNING: {errors[-1]}", file=sys.stderr)
    _link_into_venv(bin_dir, names=tuple(Path(path).name for path in installed.values()))
    if not installed:
        raise RuntimeError("; ".join(errors) or "no runtime CLIs installed")
    return installed


def _install_deepseek_harness(
    spec: dict[str, Any],
    root: Path,
    bin_dir: Path,
    *,
    force: bool,
) -> Path:
    package = str(spec["npm_package"])
    version = str(spec["npm_version"])
    dest = bin_dir / str(spec.get("default_binary") or "dsh")
    if not force and _binary_reports_version(dest, version):
        print(f"pinned deepseek-harness already present: {dest} ({version})")
        return dest
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        raise RuntimeError(
            "DeepSeek Harness needs Node.js and npm "
            f"({DSH_NODE_RANGE}). Install Node, then re-run ./setup.sh."
        )
    _require_node_range(node)
    npm_dir = root / "dsh-npm"
    npm_dir.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [npm, "install", "--omit=dev", f"{package}@{version}"],
        cwd=npm_dir,
    )
    npm_bin = npm_dir / "node_modules" / ".bin" / "dsh"
    if not npm_bin.exists():
        raise RuntimeError(f"npm install did not produce {npm_bin}")
    _replace_symlink(dest, npm_bin)
    dest.chmod(dest.stat().st_mode | 0o111)
    if not _binary_reports_version(dest, version):
        raise RuntimeError(f"installed dsh at {dest} is not {version}")
    print(f"pinned deepseek-harness: {package}@{version} -> {dest}")
    return dest


def _install_codex(
    spec: dict[str, Any],
    root: Path,
    bin_dir: Path,
    *,
    force: bool,
) -> Path:
    version = str(spec["npm_version"])
    dest = bin_dir / str(spec.get("default_binary") or "codex")
    if not force and _binary_reports_version(dest, version):
        print(f"pinned codex already present: {dest} ({version})")
        return dest
    asset = _codex_release_asset()
    tag = str(spec.get("github_release_tag") or spec["tag"])
    url = (
        "https://github.com/openai/codex/releases/download/"
        f"{tag}/{asset}"
    )
    dist_dir = root / "codex-dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    archive = dist_dir / asset
    print(f"downloading {url}")
    _download(url, archive)
    extracted = _extract_codex_archive(archive, dist_dir)
    shutil.copy2(extracted, dest)
    dest.chmod(dest.stat().st_mode | 0o111)
    if not _binary_reports_version(dest, version):
        raise RuntimeError(f"installed codex at {dest} is not {version}")
    print(f"pinned codex: {tag} ({asset}) -> {dest}")
    return dest


def _codex_release_asset(*, system: str | None = None, machine: str | None = None) -> str:
    system_name = (system or platform.system()).lower()
    cpu = (machine or platform.machine()).lower()
    if cpu in {"amd64"}:
        cpu = "x86_64"
    if cpu in {"arm64"}:
        cpu = "aarch64"
    if system_name == "darwin" and cpu == "aarch64":
        return "codex-aarch64-apple-darwin.tar.gz"
    if system_name == "darwin" and cpu == "x86_64":
        return "codex-x86_64-apple-darwin.tar.gz"
    if system_name == "linux" and cpu == "aarch64":
        return "codex-aarch64-unknown-linux-musl.tar.gz"
    if system_name == "linux" and cpu == "x86_64":
        return "codex-x86_64-unknown-linux-musl.tar.gz"
    raise RuntimeError(f"no pinned Codex binary for {system_name}/{cpu}")


def _extract_codex_archive(archive: Path, dest_dir: Path) -> Path:
    with tarfile.open(archive) as tar:
        members = [member for member in tar.getmembers() if member.isfile()]
        if not members:
            raise RuntimeError(f"{archive} has no files")
        try:
            tar.extractall(dest_dir, filter="data")
        except TypeError:
            tar.extractall(dest_dir)
    candidates = [
        dest_dir / Path(member.name).name
        for member in members
        if Path(member.name).name.startswith("codex")
    ]
    if not candidates:
        raise RuntimeError(f"{archive} did not contain a codex binary")
    binary = candidates[0]
    if not binary.is_file():
        nested = dest_dir / members[0].name
        if nested.is_file():
            return nested
        raise RuntimeError(f"extracted Codex binary missing: {binary}")
    return binary


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers=_GITHUB_HEADERS)
    with urllib.request.urlopen(request) as response, tempfile.NamedTemporaryFile(
        delete=False, dir=destination.parent
    ) as tmp:
        shutil.copyfileobj(response, tmp)
        tmp_path = Path(tmp.name)
    tmp_path.replace(destination)


def _replace_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target.resolve())


def _project_venv_bins() -> list[Path]:
    found: list[Path] = []
    default = REPO_ROOT / ".venv" / "bin"
    if default.is_dir():
        found.append(default)
    exe_bin = Path(sys.executable).resolve().parent
    try:
        exe_bin.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return found
    if exe_bin.is_dir() and exe_bin.resolve() not in {path.resolve() for path in found}:
        found.append(exe_bin)
    return found


def _link_into_venv(bin_dir: Path, *, names: tuple[str, ...]) -> None:
    for venv_bin in _project_venv_bins():
        if venv_bin.resolve() == bin_dir.resolve():
            continue
        for name in names:
            source = bin_dir / name
            if not source.exists():
                continue
            dest = venv_bin / name
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            dest.symlink_to(source.resolve())
            print(f"linked {dest} -> {source}")


def _binary_reports_version(binary: Path, version: str) -> bool:
    if not binary.exists():
        return False
    try:
        completed = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    text = f"{completed.stdout} {completed.stderr}"
    return version in text


def _require_node_range(node_bin: str) -> None:
    raw = subprocess.check_output([node_bin, "-v"], text=True).strip().lstrip("v")
    parts = raw.split(".")
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else 0
    if major == 22 and minor >= 19:
        return
    if major >= 24:
        return
    raise RuntimeError(
        f"DeepSeek Harness needs Node.js {DSH_NODE_RANGE}; found v{raw}."
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    force = False
    target = "all"
    while args:
        item = args.pop(0)
        if item in {"-h", "--help"}:
            print("Usage: install_runtime_agents.py [deepseek-harness|codex|all] [--force]")
            return 0
        if item == "--force":
            force = True
            continue
        if item.startswith("-"):
            raise SystemExit(f"unknown option: {item}")
        target = item
    installed = install_runtime_agents(target=target, force=force)
    print(json.dumps({"bin_dir": str(runtime_bin_dir()), "installed": installed}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
