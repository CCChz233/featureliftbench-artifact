"""Small helpers for the token-efficiency analysis."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence


def utc_now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        return
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]], *, gzip_out: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if gzip_out:
        handle = gzip.open(path, "wt", encoding="utf-8")
    else:
        handle = path.open("w", encoding="utf-8")
    with handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_cell(row.get(key)) for key in fieldnames})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def csv_bool(value: str | bool | None) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(f"invalid boolean {value!r}")


def git_commit(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def git_dirty(root: Path) -> bool:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return bool(completed.stdout.strip())


def docker_image_identity(image: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["docker", "inspect", image],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {"image": image, "available": False, "error": str(exc)}
    if completed.returncode != 0:
        return {
            "image": image,
            "available": False,
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }
    info = json.loads(completed.stdout)[0]
    labels = info.get("Config", {}).get("Labels") or {}
    return {
        "image": image,
        "available": True,
        "id": info.get("Id"),
        "repo_digests": info.get("RepoDigests") or [],
        "created": info.get("Created"),
        "entrypoint": info.get("Config", {}).get("Entrypoint"),
        "user": info.get("Config", {}).get("User"),
        "benchmark_id": labels.get("io.featureliftbench.benchmark-id"),
        "source_revision": labels.get("org.opencontainers.image.revision"),
    }


def hash_files(root: Path, relative_paths: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for relative in relative_paths:
        path = root / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        if path.is_file():
            digest.update(path.read_bytes())
        digest.update(b"\n")
    return digest.hexdigest()


def quantile_linear(values: Sequence[float], q: float) -> float | None:
    """NumPy ``method='linear'`` percentile on a 0–1 quantile."""

    if not values:
        return None
    ordered = sorted(float(item) for item in values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    weight = pos - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def median_linear(values: Sequence[float]) -> float | None:
    return quantile_linear(values, 0.5)


def iqr(values: Sequence[float]) -> tuple[float | None, float | None, float | None]:
    return quantile_linear(values, 0.25), median_linear(values), quantile_linear(values, 0.75)


def parse_ts(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return None


def as_int(value: Any) -> int | None:
    if value is None or value is False:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None
