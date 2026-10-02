"""Cached Docker evaluation of reconstructed submissions with validated cache keys."""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from featureliftbench.docker_eval import evaluate_submission_docker
from featureliftbench.evaluation_capsule import build_evaluation_capsule
from featureliftbench.scoring import functional_gate

from .artifacts import extract_archive
from .constants import EVAL_CODE_RELATIVE, PINNED_EVAL_IMAGE
from .scope import OfficialRun, repo_root
from .util import docker_image_identity, hash_files, read_json, sha256_text, write_json


EVAL_CONFIG = {
    "gates": ["build", "public", "hidden", "isolation"],
    "network": "none",
    "image_tag": PINNED_EVAL_IMAGE,
    "functional_only": True,
}


@dataclass
class SnapshotEvaluation:
    run_id: str
    task_id: str
    artifact_hash: str
    eval_key: str
    image_digest: str
    task_capsule_hash: str
    eval_code_hash: str
    eval_status: str
    functional_pass: bool | None
    build_pass: bool | None
    public_pass: bool | None
    hidden_pass: bool | None
    isolation_pass: bool | None
    retry_count: int
    result_path: str
    log_path: str
    cached: bool
    error: str = ""

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


class EvalCache:
    def __init__(self, cache_dir: Path, *, root: Path | None = None) -> None:
        self.cache_dir = cache_dir
        self.root = (root or repo_root()).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.eval_code_hash = hash_files(self.root, EVAL_CODE_RELATIVE)
        identity = docker_image_identity(PINNED_EVAL_IMAGE)
        self.image_digest = str(identity.get("id") or PINNED_EVAL_IMAGE)
        self.image_available = bool(identity.get("available"))
        self._capsule_hashes: dict[str, str] = {}
        self._lock = threading.Lock()

    def capsule_hash(self, task_id: str) -> str:
        lock = getattr(self, "_lock", None)
        hashes = getattr(self, "_capsule_hashes", None)
        if hashes is None:
            self._capsule_hashes = {}
            hashes = self._capsule_hashes
        if lock is None:
            cached = hashes.get(task_id)
        else:
            with lock:
                cached = hashes.get(task_id)
        if cached:
            return cached
        task_dir = self.root / "benchmark" / "tasks" / task_id
        with tempfile.TemporaryDirectory(prefix="flb-te-cap-") as tmp:
            manifest = build_evaluation_capsule(task_dir, Path(tmp) / "capsule")
        digest = str(manifest["digest"])
        if lock is None:
            hashes[task_id] = digest
        else:
            with lock:
                hashes[task_id] = digest
        return digest

    def make_eval_key(self, task_id: str, artifact_hash: str) -> str:
        payload = {
            "task_id": task_id,
            "artifact_hash": artifact_hash,
            "task_capsule_hash": self.capsule_hash(task_id),
            "image_digest": self.image_digest,
            "eval_code_hash": self.eval_code_hash,
            "eval_config": EVAL_CONFIG,
        }
        return sha256_text(json.dumps(payload, sort_keys=True))

    def lookup(self, eval_key: str) -> dict[str, Any] | None:
        result_path = self.cache_dir / eval_key / "result.json"
        meta_path = self.cache_dir / eval_key / "cache_meta.json"
        if not result_path.is_file() or not meta_path.is_file():
            return None
        try:
            result = read_json(result_path)
            meta = read_json(meta_path)
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        if meta.get("eval_key") != eval_key:
            return None
        if meta.get("image_digest") != self.image_digest:
            return None
        if meta.get("eval_code_hash") != self.eval_code_hash:
            return None
        if meta.get("eval_config") != EVAL_CONFIG:
            return None
        status = str(result.get("status") or meta.get("eval_status") or "")
        if status in {"error", "timeout", "infra_error"}:
            return None
        if meta.get("eval_status") in {"error", "timeout", "infra_error"}:
            return None
        if _eval_status(result) != "ok":
            return None
        return {"result": result, "meta": meta, "result_path": result_path}

    def evaluate_hash(
        self,
        *,
        run: OfficialRun,
        artifact_hash: str,
        cas_dir: Path,
        force: bool = False,
    ) -> SnapshotEvaluation:
        eval_key = self.make_eval_key(run.task_id, artifact_hash)
        if not force:
            hit = self.lookup(eval_key)
            if hit is not None:
                return self._from_result(
                    run=run,
                    artifact_hash=artifact_hash,
                    eval_key=eval_key,
                    result=hit["result"],
                    result_path=Path(hit["result_path"]),
                    retry_count=int(hit["meta"].get("retry_count") or 0),
                    cached=True,
                )
        archive = cas_dir / run.task_id / f"{artifact_hash}.tar.gz"
        output_dir = self.cache_dir / eval_key
        output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="flb-te-sub-") as tmp:
            submission = Path(tmp) / "submission"
            if archive.is_file():
                extract_archive(archive, submission)
            else:
                submission.mkdir()
            return self._eval_submission(
                run=run,
                artifact_hash=artifact_hash,
                eval_key=eval_key,
                submission=submission,
                output_dir=output_dir,
            )

    def evaluate_path(
        self,
        *,
        run: OfficialRun,
        artifact_hash: str,
        submission: Path,
        force: bool = False,
        label: str = "path",
    ) -> SnapshotEvaluation:
        eval_key = self.make_eval_key(run.task_id, artifact_hash)
        if not force:
            hit = self.lookup(eval_key)
            if hit is not None:
                return self._from_result(
                    run=run,
                    artifact_hash=artifact_hash,
                    eval_key=eval_key,
                    result=hit["result"],
                    result_path=Path(hit["result_path"]),
                    retry_count=int(hit["meta"].get("retry_count") or 0),
                    cached=True,
                )
        output_dir = self.cache_dir / eval_key
        output_dir.mkdir(parents=True, exist_ok=True)
        return self._eval_submission(
            run=run,
            artifact_hash=artifact_hash,
            eval_key=eval_key,
            submission=submission,
            output_dir=output_dir,
        )

    def _eval_submission(
        self,
        *,
        run: OfficialRun,
        artifact_hash: str,
        eval_key: str,
        submission: Path,
        output_dir: Path,
    ) -> SnapshotEvaluation:
        task_dir = self.root / "benchmark" / "tasks" / run.task_id
        last_error = ""
        result: dict[str, Any] = {}
        retry = 0
        for retry in range(3):
            try:
                result = evaluate_submission_docker(
                    task_dir=task_dir,
                    submission_dir=submission,
                    output_dir=output_dir,
                    image=PINNED_EVAL_IMAGE,
                    use_docker=True,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                result = {"status": "error", "errors": [last_error]}
            status = _eval_status(result)
            if status not in {"error", "timeout", "infra_error"}:
                break
            if retry >= 1:
                break
        evaluation = self._from_result(
            run=run,
            artifact_hash=artifact_hash,
            eval_key=eval_key,
            result=result,
            result_path=output_dir / "result.json",
            retry_count=retry,
            cached=False,
            error=last_error,
        )
        if evaluation.eval_status not in {"error", "timeout", "infra_error"}:
            write_json(
                output_dir / "cache_meta.json",
                {
                    "eval_key": eval_key,
                    "task_id": run.task_id,
                    "artifact_hash": artifact_hash,
                    "image_digest": self.image_digest,
                    "task_capsule_hash": self.capsule_hash(run.task_id),
                    "eval_code_hash": self.eval_code_hash,
                    "eval_config": EVAL_CONFIG,
                    "eval_status": evaluation.eval_status,
                    "retry_count": retry,
                },
            )
        elif (output_dir / "cache_meta.json").is_file():
            (output_dir / "cache_meta.json").unlink()
        return evaluation

    def _from_result(
        self,
        *,
        run: OfficialRun,
        artifact_hash: str,
        eval_key: str,
        result: dict[str, Any],
        result_path: Path,
        retry_count: int,
        cached: bool,
        error: str = "",
    ) -> SnapshotEvaluation:
        status = _eval_status(result)
        gates = _gates(result, status)
        return SnapshotEvaluation(
            run_id=run.run_id,
            task_id=run.task_id,
            artifact_hash=artifact_hash,
            eval_key=eval_key,
            image_digest=self.image_digest,
            task_capsule_hash=self.capsule_hash(run.task_id),
            eval_code_hash=self.eval_code_hash,
            eval_status=status,
            functional_pass=gates["functional_pass"],
            build_pass=gates["build_pass"],
            public_pass=gates["public_pass"],
            hidden_pass=gates["hidden_pass"],
            isolation_pass=gates["isolation_pass"],
            retry_count=retry_count,
            result_path=str(result_path),
            log_path=str(result_path.parent / "logs"),
            cached=cached,
            error=error or _error_text(result),
        )


def original_gates(run: OfficialRun) -> dict[str, bool | None]:
    mapped = Path(run.mapped_run_dir)
    path = mapped / "eval" / "result.json"
    if not path.is_file():
        return {
            "functional_pass": run.final_pass,
            "build_pass": run.build_pass,
            "public_pass": run.public_pass,
            "hidden_pass": run.hidden_pass,
            "isolation_pass": run.isolation_pass,
        }
    try:
        result = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "functional_pass": run.final_pass,
            "build_pass": run.build_pass,
            "public_pass": run.public_pass,
            "hidden_pass": run.hidden_pass,
            "isolation_pass": run.isolation_pass,
        }
    return _gates(result, _eval_status(result))


def gates_match(left: dict[str, bool | None], right: dict[str, bool | None]) -> bool:
    for key in ("functional_pass", "build_pass", "public_pass", "hidden_pass", "isolation_pass"):
        if left.get(key) != right.get(key):
            return False
    return True


def _eval_status(result: dict[str, Any]) -> str:
    sandbox = result.get("sandbox") if isinstance(result.get("sandbox"), dict) else {}
    if result.get("timed_out") or sandbox.get("timed_out"):
        return "timeout"
    if sandbox.get("docker_sandbox_error"):
        return "infra_error"
    status = str(result.get("status") or "")
    if status in {"error", "timeout"}:
        return status
    errors = result.get("errors") or []
    if any("dependency installation failed" in str(error).lower() for error in errors):
        return "infra_error"
    if status in {"failed", "passed"} or "build_pass" in result:
        return "ok" if status != "error" else "error"
    if errors and status not in {"failed", "passed"}:
        return "error"
    return status or "ok"


def _gates(result: dict[str, Any], status: str) -> dict[str, bool | None]:
    if status in {"error", "timeout", "infra_error"}:
        return {
            "functional_pass": None,
            "build_pass": None,
            "public_pass": None,
            "hidden_pass": None,
            "isolation_pass": None,
        }
    build = _as_bool(result.get("build_pass"))
    public = _as_bool(result.get("public_tests_pass", result.get("public_pass")))
    hidden = _as_bool(result.get("hidden_tests_pass", result.get("hidden_pass")))
    isolation = _as_bool(result.get("isolation_pass"))
    scores = result.get("scores") if isinstance(result.get("scores"), dict) else {}
    functional = _as_bool(scores.get("functional_gate"))
    if functional is None and None not in {build, public, hidden, isolation}:
        functional = bool(
            functional_gate(
                build_pass=bool(build),
                public_tests_pass=public,
                hidden_tests_pass=hidden,
                isolation_pass=isolation,
            )
        )
    elif scores.get("functional_gate") in {0, 0.0, 1, 1.0}:
        functional = bool(scores.get("functional_gate"))
    return {
        "functional_pass": functional,
        "build_pass": build,
        "public_pass": public,
        "hidden_pass": hidden,
        "isolation_pass": isolation,
    }


def _as_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if value in {0, 0.0, "0", "false", "False"}:
        return False
    if value in {1, 1.0, "1", "true", "True"}:
        return True
    return bool(value)


def _error_text(result: dict[str, Any]) -> str:
    errors = result.get("errors")
    if isinstance(errors, list) and errors:
        return "; ".join(str(item) for item in errors[:5])
    return str(result.get("message") or "")
