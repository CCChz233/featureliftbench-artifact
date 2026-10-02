"""Package delivery tarballs without secrets or original donor repos."""

from __future__ import annotations

import hashlib
import shutil
import tarfile
from pathlib import Path
from typing import Any

from .constants import METHOD_VERSION, PINNED_EVAL_IMAGE, PINNED_REPLAY_IMAGE
from .scope import repo_root
from .util import git_commit, sha256_file, utc_now_stamp, write_json


DELIVERY_FILES = (
    "README.md",
    "REPORT.md",
    "manifest.json",
    "verification.json",
    "coverage.csv",
    "run_manifest.csv",
    "pilot_manifest.csv",
    "calls.jsonl.gz",
    "artifact_timeline.jsonl.gz",
    "snapshot_evaluations.csv",
    "run_metrics.csv",
    "summary_by_configuration.csv",
    "summary_by_lift_type.csv",
    "pass_fail_effort.csv",
    "coverage_bias.csv",
    "sensitivity.csv",
    "unresolved.csv",
)


def package_delivery(
    *,
    inventory_dir: Path,
    pilot_dir: Path,
    full_dir: Path,
    output_dir: Path,
    root: Path | None = None,
) -> dict[str, Any]:
    base = (root or repo_root()).resolve()
    stamp = utc_now_stamp()
    staging = output_dir / f"token_efficiency_delivery_{stamp}"
    evidence = output_dir / f"token_efficiency_evidence_{stamp}"
    staging.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)

    _copy_if(full_dir / "REPORT.md", staging / "REPORT.md")
    _copy_if(full_dir / "run_metrics.csv", staging / "run_metrics.csv")
    if (inventory_dir / "run_manifest.csv").is_file():
        _copy_if(inventory_dir / "run_manifest.csv", staging / "run_manifest.csv")
    else:
        _copy_if(full_dir / "run_manifest.csv", staging / "run_manifest.csv")
    _copy_if(inventory_dir / "coverage.csv", staging / "coverage.csv")
    if (full_dir / "unresolved.csv").is_file():
        _copy_if(full_dir / "unresolved.csv", staging / "unresolved.csv")
    else:
        _copy_if(inventory_dir / "unresolved.csv", staging / "unresolved.csv")
    _copy_if(pilot_dir / "pilot_manifest.csv", staging / "pilot_manifest.csv")
    for name in (
        "summary_by_configuration.csv",
        "summary_by_lift_type.csv",
        "pass_fail_effort.csv",
        "coverage_bias.csv",
        "sensitivity.csv",
        "REPORT.md",
    ):
        _copy_if(full_dir / name, staging / name)
    if (full_dir / "figures").is_dir():
        shutil.copytree(full_dir / "figures", staging / "figures", dirs_exist_ok=True)
    if (full_dir / "paper_ready").is_dir():
        shutil.copytree(full_dir / "paper_ready", staging / "paper_ready", dirs_exist_ok=True)

    _concat_jsonl_gz(full_dir / "runs", "calls.jsonl", staging / "calls.jsonl.gz")
    _concat_jsonl_gz(full_dir / "runs", "artifact_timeline.jsonl", staging / "artifact_timeline.jsonl.gz")
    _concat_eval_csv(full_dir / "runs", staging / "snapshot_evaluations.csv", repo=base)
    _write_accounting_sensitivity(staging / "calls.jsonl.gz", staging / "run_metrics.csv", staging / "sensitivity_accounting.csv")
    _copy_code(base, staging / "code")
    _write_patch(base, staging / "code.patch")
    _write_examples(full_dir, staging / "examples")
    _copy_freeze_inputs(base, staging / "freeze")
    _write_dependencies(staging / "code" / "DEPENDENCIES.txt")
    _write_eval_replay(staging / "EVAL_REPLAY.md")
    _copy_usage_probe(full_dir.parent / "usage_probe", staging / "usage_probe")
    _render_figures(staging / "figures")
    if (staging / "paper_ready").is_dir() and (staging / "figures" / "psf_ecdf.png").is_file():
        for name in ("psf_ecdf.png", "psf_ecdf.pdf", "token_steps.png", "token_steps.pdf"):
            src = staging / "figures" / name
            if src.is_file():
                shutil.copy2(src, staging / "paper_ready" / name)

    manifest = {
        "method_version": METHOD_VERSION,
        "git_commit": git_commit(base),
        "created_utc": stamp,
        "inventory_dir": _relpath(inventory_dir, base),
        "pilot_dir": _relpath(pilot_dir, base),
        "full_dir": _relpath(full_dir, base),
        "pinned_eval_image": PINNED_EVAL_IMAGE,
        "pinned_replay_image": PINNED_REPLAY_IMAGE,
        "official_pass_counts": {
            "deepseek-v4-pro": 115,
            "deepseek-v4-flash": 108,
            "gpt-5.6-luna": 102,
            "glm-5.3-flash": 68,
            "qwen3.6-35b-a3b-fp8": 63,
            "gpt-oss-120b": 36,
        },
    }
    write_json(staging / "manifest.json", manifest)
    verification = _run_verification(staging, base)
    write_json(staging / "verification.json", verification)
    write_json(full_dir / "verification.json", verification)
    src_readme = full_dir.parent / "README.md"
    if src_readme.is_file():
        (staging / "README.md").write_text(
            src_readme.read_text(encoding="utf-8") + "\n\n" + _readme(stamp, manifest),
            encoding="utf-8",
        )
    else:
        (staging / "README.md").write_text(_readme(stamp, manifest), encoding="utf-8")

    if (full_dir.parent / "cas").is_dir():
        shutil.copytree(full_dir.parent / "cas", evidence / "cas", dirs_exist_ok=True)
    if (full_dir.parent / "eval_cache").is_dir():
        shutil.copytree(full_dir.parent / "eval_cache", evidence / "eval_cache", dirs_exist_ok=True)
    _copy_if(staging / "snapshot_evaluations.csv", evidence / "snapshot_evaluations.csv")
    _copy_freeze_inputs(base, evidence / "freeze")
    _write_eval_replay(evidence / "EVAL_REPLAY.md")
    _write_by_run_index(full_dir / "runs", staging / "snapshot_evaluations.csv", evidence)
    (evidence / "README.md").write_text(
        "Private reconstruction evidence.\n\n"
        "- `cas/` content-addressed reconstructed submissions.\n"
        "- `eval_cache/<eval_key>/` pinned-image evaluator result/logs.\n"
        "- `by_run/<configuration>/<task_id>/` per-run metrics pointers (run_id).\n"
        "- `INDEX.csv` maps run_id + artifact_hash to eval_cache keys.\n"
        "- `freeze/` official membership and paper_sources (no secrets).\n"
        "Do not mix private hidden-test logs into public examples.\n"
        "Hidden-test stdout under eval_cache is private.\n",
        encoding="utf-8",
    )

    delivery_tar = output_dir / f"token_efficiency_delivery_{stamp}.tar.gz"
    evidence_tar = output_dir / f"token_efficiency_evidence_{stamp}.tar.gz"
    _tar_dir(staging, delivery_tar)
    _tar_dir(evidence, evidence_tar)
    checksums = {
        "delivery": {
            "filename": delivery_tar.name,
            "path": _relpath(delivery_tar, base),
            "sha256": sha256_file(delivery_tar),
        },
        "evidence": {
            "filename": evidence_tar.name,
            "path": _relpath(evidence_tar, base),
            "sha256": sha256_file(evidence_tar),
        },
    }
    write_json(output_dir / f"token_efficiency_checksums_{stamp}.json", checksums)
    (output_dir / "DOWNLOAD.md").write_text(
        "\n".join(
            [
                "# Token-efficiency handoff (runbook §8)",
                "",
                "Official Python-150 900-run offline analysis. Does not replace Table 1 `--` for Luna/GLM.",
                "",
                f"- Main pack: `{delivery_tar.name}`",
                f"  sha256 `{checksums['delivery']['sha256']}`",
                f"- Evidence pack: `{evidence_tar.name}`",
                f"  sha256 `{checksums['evidence']['sha256']}`",
                "",
                "Download these two `.tar.gz` files. Evidence contains private hidden-test logs.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return checksums


def _copy_if(src: Path, dest: Path) -> None:
    if src.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def _run_verification(staging: Path, root: Path) -> dict[str, Any]:
    import tempfile

    from .scope import load_official_runs
    from .summarize import summarize_suite
    from .util import read_csv

    result: dict[str, Any] = {
        "summary_rebuild": {"status": "not_run"},
        "offline_eval_replay": {
            "status": "partial",
            "reason": (
                "Pilot 20/20 final four-gate re-eval matched original labels. "
                "The full 900 used the same pinned evaluator image and cache; "
                "the packager does not re-run Docker or model APIs. "
                "See EVAL_REPLAY.md."
            ),
            "pinned_eval_image": PINNED_EVAL_IMAGE,
        },
        "png_pdf_figures": {"status": "not_run"},
    }
    metrics_path = staging / "run_metrics.csv"
    summary_path = staging / "summary_by_configuration.csv"
    if not metrics_path.is_file() or not summary_path.is_file():
        result["summary_rebuild"] = {"status": "failed", "reason": "missing csv"}
        return result
    try:
        rows = read_csv(metrics_path)
        runs = load_official_runs(root)
        with tempfile.TemporaryDirectory(prefix="flb-te-rebuild-") as tmp:
            summarize_suite(metrics_rows=rows, runs=runs, output_dir=Path(tmp))
            rebuilt = (Path(tmp) / "summary_by_configuration.csv").read_text(encoding="utf-8")
            original = summary_path.read_text(encoding="utf-8")
            result["summary_rebuild"] = {
                "status": "passed" if rebuilt == original else "failed",
                "n_rows": len(rows),
                "matches_packaged_summary": rebuilt == original,
            }
    except Exception as exc:  # noqa: BLE001
        result["summary_rebuild"] = {
            "status": "failed",
            "reason": f"{type(exc).__name__}: {exc}",
        }
    png = staging / "figures" / "psf_ecdf.png"
    pdf = staging / "figures" / "psf_ecdf.pdf"
    result["png_pdf_figures"] = {
        "status": "passed" if png.is_file() and pdf.is_file() else "partial",
        "psf_ecdf_png": png.is_file(),
        "psf_ecdf_pdf": pdf.is_file(),
        "token_steps_png": (staging / "figures" / "token_steps.png").is_file(),
        "token_steps_pdf": (staging / "figures" / "token_steps.pdf").is_file(),
    }
    return result


def _concat_jsonl_gz(runs_root: Path, filename: str, dest: Path) -> None:
    import gzip
    import json

    dest.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(dest, "wt", encoding="utf-8") as out:
        if not runs_root.is_dir():
            return
        for path in sorted(runs_root.glob(f"*/*/{filename}")):
            configuration = path.parent.parent.name
            task_id = path.parent.name
            run_id = f"{configuration}/{task_id}"
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    out.write(line + "\n")
                    continue
                if isinstance(payload, dict):
                    payload.setdefault("run_id", run_id)
                    payload.setdefault("configuration", configuration)
                    payload.setdefault("task_id", task_id)
                    out.write(json.dumps(payload, sort_keys=True) + "\n")
                else:
                    out.write(line + "\n")


def _concat_eval_csv(runs_root: Path, dest: Path, *, repo: Path) -> None:
    import csv
    import json

    dest.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_id",
        "task_id",
        "artifact_hash",
        "eval_key",
        "image_digest",
        "task_capsule_hash",
        "eval_code_hash",
        "eval_status",
        "functional_pass",
        "build_pass",
        "public_pass",
        "hidden_pass",
        "isolation_pass",
        "retry_count",
        "result_path",
        "log_path",
    ]
    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if not runs_root.is_dir():
            return
        for path in sorted(runs_root.glob("*/*/snapshot_evaluations.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for row in payload.values():
                out = {key: row.get(key, "") for key in fieldnames}
                out["result_path"] = _cache_relpath(str(out.get("result_path") or ""), repo)
                out["log_path"] = _cache_relpath(str(out.get("log_path") or ""), repo)
                writer.writerow(out)


def _copy_code(root: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    src = root / "harness" / "featureliftbench" / "token_efficiency"
    shutil.copytree(src, dest / "token_efficiency", dirs_exist_ok=True)
    script = root / "harness" / "scripts" / "analyze_token_efficiency_current.py"
    if script.is_file():
        shutil.copy2(script, dest / "analyze_token_efficiency_current.py")
    tests = root / "harness" / "tests" / "test_token_efficiency.py"
    if tests.is_file():
        shutil.copy2(tests, dest / "test_token_efficiency.py")
    (dest / "PATHS.txt").write_text(
        "token_efficiency/ -> harness/featureliftbench/token_efficiency/\n"
        "analyze_token_efficiency_current.py -> harness/scripts/\n"
        "test_token_efficiency.py -> harness/tests/\n"
        "DEPENDENCIES.txt -> runtime versions recorded at packaging\n",
        encoding="utf-8",
    )


def _write_patch(root: Path, dest: Path) -> None:
    import subprocess

    files: list[Path] = []
    package = root / "harness" / "featureliftbench" / "token_efficiency"
    if package.is_dir():
        files.extend(sorted(path for path in package.rglob("*.py") if path.is_file()))
    for relative in (
        "harness/scripts/analyze_token_efficiency_current.py",
        "harness/tests/test_token_efficiency.py",
    ):
        path = root / relative
        if path.is_file():
            files.append(path)
    chunks: list[str] = []
    for path in files:
        completed = subprocess.run(
            ["git", "diff", "--no-index", "--", "/dev/null", str(path.relative_to(root))],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.stdout:
            chunks.append(completed.stdout)
    if chunks:
        dest.write_text("".join(chunks), encoding="utf-8")
        return
    preexisting = root / "reports" / "paper_analysis" / "token_efficiency_current" / "code.patch"
    if preexisting.is_file() and preexisting.stat().st_size > 0:
        dest.write_text(preexisting.read_text(encoding="utf-8"), encoding="utf-8")
        return
    dest.write_text("", encoding="utf-8")


def _write_examples(full_dir: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    source = full_dir.parent / "examples"
    if source.is_dir():
        shutil.copytree(source, dest, dirs_exist_ok=True)
    readme = dest / "README.md"
    if not readme.is_file():
        readme.write_text(
            "Examples are pointers into run_metrics.csv. Private logs stay in the evidence pack.\n"
            "Pilot examples must not be cited as official 900-run prevalence.\n",
            encoding="utf-8",
        )


def _relpath(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _cache_relpath(path: str, repo: Path) -> str:
    if not path:
        return ""
    marker = "/token_efficiency_current/"
    if marker in path:
        return path.split(marker, 1)[1]
    try:
        return str(Path(path).resolve().relative_to(repo.resolve()))
    except Exception:
        return path


def _write_dependencies(dest: Path) -> None:
    import platform
    import sys

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "\n".join(
            [
                f"python={sys.version.split()[0]}",
                f"platform={platform.platform()}",
                "analysis_runtime=python3.12 stdlib + tomllib",
                "figure_runtime=python3 matplotlib (optional; JSON always shipped)",
                f"pinned_eval_image={PINNED_EVAL_IMAGE}",
                f"pinned_replay_image={PINNED_REPLAY_IMAGE}",
                "forbidden_eval_image=featureliftbench-eval:latest",
                "no_pip_packages_required_for_summary_rebuild",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_eval_replay(dest: Path) -> None:
    dest.write_text(
        f"""# Offline evaluator replay (separate from summary rebuild)

Pinned image: `{PINNED_EVAL_IMAGE}` (never `latest`).
Replay/agent image: `{PINNED_REPLAY_IMAGE}`.

The packager does not re-run Docker. Pilot 20/20 four-gate re-eval already
matched original labels. Full 900 snapshot evals used the same image digest
recorded in `snapshot_evaluations.csv`.

Example (from the FeatureLiftBench repo, not from this tarball alone):

```bash
PYTHONPATH=harness python3.12 -B -m featureliftbench.cli eval \\
  benchmark/tasks/<task_id> <submission_dir> \\
  --docker --docker-image {PINNED_EVAL_IMAGE} \\
  --output <eval_out>
```

Functional Pass = build ∧ public ∧ hidden ∧ isolation. Empty submissions fail.
Do not cache evaluator errors as fail.
""",
        encoding="utf-8",
    )


def _copy_freeze_inputs(root: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for relative in (
        "docs/paper/writing/python150_membership.json",
        "docs/paper/paper_sources.json",
        "docs/paper/experiments/TOKEN_EFFICIENCY_SERVER_RUNBOOK.md",
    ):
        src = root / relative
        if src.is_file():
            shutil.copy2(src, dest / Path(relative).name)


def _copy_usage_probe(src: Path, dest: Path) -> None:
    if not src.is_dir():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for name in (
        "README.md",
        "probe_result.json",
        "probe_result_r5.json",
        "provider_diagnostic.json",
    ):
        _copy_if(src / name, dest / name)


def _write_by_run_index(runs_root: Path, snapshot_csv: Path, evidence: Path) -> None:
    import csv

    index = evidence / "INDEX.csv"
    fieldnames = [
        "run_id",
        "configuration",
        "task_id",
        "artifact_hash",
        "eval_key",
        "eval_status",
        "functional_pass",
        "eval_cache_relpath",
    ]
    with index.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if snapshot_csv.is_file():
            for row in csv.DictReader(snapshot_csv.open(encoding="utf-8")):
                run_id = str(row.get("run_id") or "")
                configuration, _, task_id = run_id.partition("/")
                eval_key = str(row.get("eval_key") or "")
                writer.writerow(
                    {
                        "run_id": run_id,
                        "configuration": configuration,
                        "task_id": task_id or row.get("task_id", ""),
                        "artifact_hash": row.get("artifact_hash", ""),
                        "eval_key": eval_key,
                        "eval_status": row.get("eval_status", ""),
                        "functional_pass": row.get("functional_pass", ""),
                        "eval_cache_relpath": f"eval_cache/{eval_key}" if eval_key else "",
                    }
                )
    if not runs_root.is_dir():
        return
    for metrics in runs_root.glob("*/*/metrics.json"):
        configuration = metrics.parent.parent.name
        task_id = metrics.parent.name
        dest_dir = evidence / "by_run" / configuration / task_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(metrics, dest_dir / "metrics.json")
        for name in ("identity.json", "final_reeval.json", "replay.json"):
            src = metrics.parent / name
            if src.is_file():
                shutil.copy2(src, dest_dir / name)


def _write_accounting_sensitivity(calls_gz: Path, metrics_csv: Path, dest: Path) -> None:
    import csv
    import gzip
    import json
    from collections import defaultdict

    totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {"n_calls": 0, "total_tokens": 0.0, "main_table_tokens": 0.0}
    )
    if calls_gz.is_file():
        with gzip.open(calls_gz, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                run_id = str(payload.get("run_id") or "")
                if not run_id:
                    continue
                bucket = totals[run_id]
                bucket["n_calls"] += 1
                if payload.get("total_tokens") is not None:
                    bucket["total_tokens"] += float(payload["total_tokens"])
                if payload.get("main_table_tokens") is not None:
                    bucket["main_table_tokens"] += float(payload["main_table_tokens"])
    rows = []
    if metrics_csv.is_file():
        for row in csv.DictReader(metrics_csv.open(encoding="utf-8")):
            run_id = str(row.get("run_id") or "")
            ledger = totals.get(run_id, {"n_calls": 0, "total_tokens": 0.0, "main_table_tokens": 0.0})
            metric_total = row.get("total_tokens") or ""
            rows.append(
                {
                    "run_id": run_id,
                    "configuration": row.get("configuration", ""),
                    "include_psf_primary": row.get("include_psf_primary", ""),
                    "metrics_total_tokens": metric_total,
                    "calls_total_tokens": ledger["total_tokens"] or "",
                    "calls_main_table_tokens": ledger["main_table_tokens"] or "",
                    "n_calls": ledger["n_calls"],
                }
            )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "run_id",
                "configuration",
                "include_psf_primary",
                "metrics_total_tokens",
                "calls_total_tokens",
                "calls_main_table_tokens",
                "n_calls",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _render_figures(figures: Path) -> None:
    import subprocess

    figures.mkdir(parents=True, exist_ok=True)
    ecdf = figures / "psf_ecdf.json"
    steps = figures / "token_steps.json"
    if not ecdf.is_file() or not steps.is_file():
        return
    script = r"""
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as exc:
    (root / "README.md").write_text(f"matplotlib unavailable: {exc}\nJSON point data were written instead.\n")
    raise SystemExit(0)

DISPLAY = {
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "gpt-5.6-luna": "GPT-5.6 Luna",
    "glm-5.3-flash": "GLM-5.3-Flash",
    "qwen3.6-35b-a3b-fp8": "Qwen3.6-35B-A3B-FP8",
    "gpt-oss-120b": "GPT-OSS 120B",
}
ORDER = list(DISPLAY)
ecdf = json.loads((root / "psf_ecdf.json").read_text())
steps = json.loads((root / "token_steps.json").read_text())
fig, ax = plt.subplots(figsize=(7.2, 4.4))
for model in ORDER:
    xs = [item["psf"] for item in ecdf if item["configuration"] == model]
    ys = [item["ecdf"] for item in ecdf if item["configuration"] == model]
    if xs:
        ax.step(xs, ys, where="post", label=DISPLAY[model])
ax.set_xlabel("Post-sufficiency fraction (Ttotal − T*) / Ttotal")
ax.set_ylabel("Cumulative proportion")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.legend(fontsize=8)
ax.set_title("PSF ECDF (primary sample, total tokens)")
fig.tight_layout()
fig.savefig(root / "psf_ecdf.png", dpi=160)
fig.savefig(root / "psf_ecdf.pdf")
plt.close(fig)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
for model in ORDER:
    pts = [item for item in steps if item["configuration"] == model]
    ax.scatter([p["steps"] for p in pts if p["final_pass"]], [p["tokens"] for p in pts if p["final_pass"]], s=12, alpha=0.7, label=f"{DISPLAY[model]} pass")
    ax.scatter([p["steps"] for p in pts if not p["final_pass"]], [p["tokens"] for p in pts if not p["final_pass"]], s=12, alpha=0.4, marker="x", label=f"{DISPLAY[model]} fail")
ax.set_xlabel("Assistant steps")
ax.set_ylabel("Total tokens")
ax.legend(fontsize=6, ncol=2)
ax.set_title("Token–steps (descriptive association only)")
fig.tight_layout()
fig.savefig(root / "token_steps.png", dpi=160)
fig.savefig(root / "token_steps.pdf")
plt.close(fig)
(root / "README.md").write_text("psf_ecdf.png/pdf: primary PSF ECDF. token_steps.png/pdf: exploratory.\n")
"""
    completed = subprocess.run(
        ["python3", "-c", script, str(figures)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 and not (figures / "README.md").is_file():
        (figures / "README.md").write_text(
            "matplotlib render failed; JSON point data were written instead.\n"
            f"{completed.stderr[-500:]}\n",
            encoding="utf-8",
        )


def _tar_dir(source: Path, dest: Path) -> None:
    with tarfile.open(dest, "w:gz") as handle:
        handle.add(source, arcname=source.name)


def _readme(stamp: str, manifest: dict[str, Any]) -> str:
    return f"""# Token efficiency delivery {stamp}

Method: {manifest.get('method_version')}
Git commit: {manifest.get('git_commit')}

## Commands actually used

```bash
PYTHONPATH=harness python3.12 -B harness/scripts/analyze_token_efficiency_current.py inventory --manifest docs/paper/paper_sources.json --output reports/paper_analysis/token_efficiency_current/inventory
PYTHONPATH=harness python3.12 -B harness/scripts/analyze_token_efficiency_current.py pilot --seed 20260916 --output reports/paper_analysis/token_efficiency_current/pilot
PYTHONPATH=harness python3.12 -B harness/scripts/analyze_token_efficiency_current.py parse-spotcheck --output reports/paper_analysis/token_efficiency_current/spotcheck_parse
PYTHONPATH=harness python3.12 -B harness/scripts/analyze_token_efficiency_current.py run --scope paper150 --resume --workers 8 --output reports/paper_analysis/token_efficiency_current/full
PYTHONPATH=harness python3.12 -B harness/scripts/analyze_token_efficiency_current.py progress --input reports/paper_analysis/token_efficiency_current/full
PYTHONPATH=harness python3.12 -B harness/scripts/analyze_token_efficiency_current.py summarize --input reports/paper_analysis/token_efficiency_current/full
PYTHONPATH=harness python3.12 -B harness/scripts/analyze_token_efficiency_current.py package --input reports/paper_analysis/token_efficiency_current/full
```

Pinned evaluator: `featureliftbench-eval:python200-prime-212930ea` (never `latest`).
Pinned replay image: `featureliftbench-agent:python200-prime-212930ea`.
Resume is per-run under `full/runs/<configuration>/<task_id>/metrics.json`.
Shared eval cache keys include task_id, artifact hash, capsule hash, image digest, eval code hash, and eval config.

Do not treat file presence as a claim that RQ5 is supported. See paper_ready/readiness.json.
"""
