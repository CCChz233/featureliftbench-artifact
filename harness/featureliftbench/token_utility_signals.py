"""Runtime-legal token-utility signals.

Offline analysis only. Features are computed from history at time t and must
not include T*, Hidden, or evaluator outcomes. Labels are attached separately.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Iterator

from featureliftbench.token_utility_replay import (
    EDITOR_WRITE_COMMANDS,
    PYTEST_RE,
    iter_jsonl,
    load_billed_calls,
    observation_text,
    parse_ts,
    tokens_at,
)

CATS = [
    "package_write",
    "self_test_write",
    "self_test_run",
    "inspect_repo",
    "inspect_upstream_tests",
    "inspect_submission",
    "inspect_spec",
    "isolation_check",
    "cleanup",
    "meta",
    "finish",
    "other",
]

INSPECT_CATS = frozenset(
    {
        "inspect_repo",
        "inspect_upstream_tests",
        "inspect_submission",
        "inspect_spec",
    }
)
SELF_TEST_CATS = frozenset({"self_test_run", "self_test_write"})

LEGAL_FEATURE_KEYS = (
    "consecutive_self_tests",
    "self_test_cmd_novel",
    "self_test_out_novel",
    "self_test_pair_novel",
    "frac_recent_self_test_out_novel",
    "tokens_since_last_useful_write",
    "steps_since_last_useful_write",
    "repeat_command_rate",
    "repeat_read_rate",
    "recent_new_trees",
)

REFERENCE_FEATURE_KEYS = (
    "unique_trees_so_far",
    "last_tree_n_bytes",
)

COMPUTED_FEATURE_KEYS = LEGAL_FEATURE_KEYS + REFERENCE_FEATURE_KEYS

FORBIDDEN_FEATURE_SUBSTR = (
    "tstar",
    "t_star",
    "earliest",
    "hidden",
    "functional_gate",
    "gold",
    "pass_tokens",
    "already_enough",
    "still_necessary",
)

WINDOW_K = 8
LOOKAHEAD_ACTIONS = 20
NEW_TREE_SOON_TOKENS = 250_000
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[()].|\r")
TIME_RE = re.compile(
    r"(\bin\s+)\d+\.\d+\s*s\b|\b\d+\.\d+\s*(seconds?|secs?|ms|s)\b",
    re.IGNORECASE,
)
HEX_RE = re.compile(r"\b[0-9a-f]{8,}\b", re.IGNORECASE)
HEREDOC_START_RE = re.compile(r"<<\s*['\"]?\w+['\"]?")
PYTHON_C_RE = re.compile(
    r"(python3?\s+-c\s+)(['\"])(?:\\.|(?!\2).)*\2",
    re.DOTALL,
)
PYTEST_COUNT_RE = re.compile(
    r"(\d+)\s+(passed|failed|errors?|skipped|warnings?)",
    re.IGNORECASE,
)


def classify(tool: str, command: str, path: str, summary: str) -> str:
    tool = (tool or "").lower()
    cmd = command or ""
    blob = f"{path} {summary} {cmd}".replace("\\", "/")
    low = blob.lower()
    if tool == "finish":
        return "finish"
    if tool in {"think", "task_tracker"}:
        return "meta"
    pkg = "submission/featurelifted" in blob or "/featurelifted/" in blob
    repo = (
        "/repo/" in blob
        or blob.startswith("repo/")
        or " repo/" in blob
        or "/flb/workspace/repo" in blob
    )
    testfile = bool(
        re.search(
            r"test_featurelifted|test_local|test_task|test_upstream|run_my_tests|/tmp/.*test|tests/test_",
            low,
        )
    )
    if tool == "file_editor":
        action_cmd = (command or "").strip().lower()
        fname = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if action_cmd in EDITOR_WRITE_COMMANDS or action_cmd == "":
            if "agents.md" in fname:
                return "meta"
            if testfile or fname.startswith("test") or "test" in fname:
                return "self_test_write"
            if pkg:
                return "package_write"
            return "other"
        if action_cmd == "view":
            if "tests/" in blob or fname.startswith("test"):
                return "inspect_upstream_tests" if repo else "inspect_submission"
            if pkg:
                return "inspect_submission"
            if repo:
                return "inspect_repo"
            return "inspect_spec"
        return "other"
    if "pip install" in low:
        return "other"
    if PYTEST_RE.search(cmd) or re.search(r"python3?\s+-m\s+unittest", cmd):
        return "self_test_run"
    if re.search(r"python3?\s+(-c|-\s*<<|<<)", cmd) or re.search(r"python3?\s+/tmp/", cmd):
        return "self_test_run"
    if re.search(r"python3?\s+\S+\.py", cmd) and re.search(r"test|pytest", low):
        return "self_test_run"
    if re.search(r"python3?\s+\S*(test|diffcheck)", cmd, re.I):
        return "self_test_run"
    if testfile and re.search(r"(cat\s*>|<<)", cmd):
        return "self_test_write"
    if re.search(r"\b(cp|mv|sed\s+-i)\b", cmd) and pkg and not testfile:
        return "package_write"
    if re.search(r"grep\s+-n.*\b(from |import )|forbidden|no \w+ import", low) or (
        "grep" in cmd and pkg and re.search(r"import |from ", cmd)
    ):
        return "isolation_check"
    if cmd.strip().startswith("rm ") and "/tmp" in cmd:
        return "cleanup"
    if re.search(r"\b(ls|find|cat|head|tail|sed\s+-n|wc|grep|rg)\b", cmd):
        if ("tests/" in blob or "test_" in low) and repo:
            return "inspect_upstream_tests"
        if pkg and not repo:
            return "inspect_submission"
        if repo:
            return "inspect_repo"
        if "task.md" in low or "metadata.json" in low:
            return "inspect_spec"
        if pkg:
            return "inspect_submission"
        return "inspect_repo" if repo or "repo" in low else "other"
    if pkg and re.search(r"\b(mkdir|touch)\b", cmd):
        return "package_write"
    return "other"


def action_fields(ev: dict[str, Any]) -> tuple[str, str, str, str]:
    action = ev.get("action") if isinstance(ev.get("action"), dict) else {}
    return (
        str(ev.get("tool_name") or ""),
        str(action.get("command") or ""),
        str(action.get("path") or action.get("file_path") or ""),
        str(ev.get("summary") or ""),
    )


def normalize_command(command: str) -> str:
    return " ".join((command or "").split())


def normalize_observation(text: str) -> str:
    cleaned = ANSI_RE.sub("", text or "")
    cleaned = TIME_RE.sub(" <t> ", cleaned)
    cleaned = HEX_RE.sub("<hex>", cleaned)
    return " ".join(cleaned.split())


def normalize_path(path: str) -> str:
    text = (path or "").replace("\\", "/")
    for prefix in ("/flb/workspace/", "/workspace/", "/data1/"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip()


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def command_skeleton(command: str) -> str:
    """Drop heredoc / python -c bodies so reruns of the same probe collide."""
    text = command or ""
    match = HEREDOC_START_RE.search(text)
    if match:
        text = text[: match.start()] + "<<HEREDOC"
    text = PYTHON_C_RE.sub(r"\1<CODE>", text)
    return normalize_command(text)


def outcome_fingerprint(text: str, exit_code: Any = None) -> str:
    cleaned = normalize_observation(text)
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for amount, kind in PYTEST_COUNT_RE.findall(cleaned):
        key = "error" if kind.lower().startswith("error") else kind.lower()
        if key in counts:
            counts[key] = int(amount)
    pytest_like = (
        any(counts.values())
        or " passed" in f" {cleaned.lower()}"
        or " failed" in f" {cleaned.lower()}"
        or "=====" in cleaned
    )
    if pytest_like:
        return (
            f"exit={exit_code}|"
            f"p={counts['passed']}/f={counts['failed']}/"
            f"e={counts['error']}/s={counts['skipped']}"
        )
    return f"exit={exit_code}|body={cleaned[-800:]}"


def command_hash(command: str) -> str:
    return short_hash(command_skeleton(command))


def observation_hash(text: str, exit_code: Any = None) -> str:
    return short_hash(outcome_fingerprint(text, exit_code))


def pair_hash(cmd_hash: str, out_hash: str) -> str:
    return short_hash(f"{cmd_hash}:{out_hash}")


def assert_legal_features(features: dict[str, Any]) -> None:
    keys = {str(key).lower() for key in features}
    for key in keys:
        for needle in FORBIDDEN_FEATURE_SUBSTR:
            if needle in key:
                raise ValueError(f"illegal feature key {key!r}")
    extra = set(features) - set(COMPUTED_FEATURE_KEYS)
    if extra:
        raise ValueError(f"unexpected feature keys: {sorted(extra)}")
    missing = set(LEGAL_FEATURE_KEYS) - set(features)
    if missing:
        raise ValueError(f"missing legal feature keys: {sorted(missing)}")


def label_still_necessary(tokens: int | None, t_star: int) -> int | None:
    """y=1 if t < T* (still necessary). None if tokens missing."""
    if tokens is None:
        return None
    return int(int(tokens) < int(t_star))


def label_already_enough(tokens: int | None, t_star: int) -> int | None:
    """y=1 if t >= T* (already sufficient). None if tokens missing."""
    if tokens is None:
        return None
    return int(int(tokens) >= int(t_star))


def iter_gold_pass_reports(phase1: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any], dict[str, Any]]]:
    for payload in phase1.get("reports") or []:
        suite = str(payload.get("suite") or "")
        for report in payload.get("reports") or []:
            summary = report.get("summary") or {}
            if not report.get("replay_ok"):
                continue
            if summary.get("original_functional_gate") != 1.0:
                continue
            if summary.get("earliest_pass_tokens") is None:
                continue
            yield suite, report, summary


def load_paired_actions(
    task_dir: Path,
) -> tuple[list[tuple[float, int, int]], list[dict[str, Any]]]:
    events_path = task_dir / "agent" / "openhands_events.jsonl"
    audit_path = task_dir / "agent" / "context_audit.jsonl"
    calls = load_billed_calls(audit_path)
    actions: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None

    def flush(action_ev: dict[str, Any], obs_ev: dict[str, Any] | None) -> None:
        tool, command, path, summary = action_fields(action_ev)
        observation = {}
        if obs_ev and isinstance(obs_ev.get("observation"), dict):
            observation = obs_ev["observation"]
        obs_text = observation_text(observation) if observation else ""
        exit_code = observation.get("exit_code")
        ts = parse_ts((obs_ev or action_ev).get("timestamp"))
        cat = classify(tool, command, path, summary)
        cmd_h = command_hash(command) if command.strip() else ""
        out_h = observation_hash(obs_text, exit_code) if obs_text or exit_code is not None else ""
        path_key = normalize_path(path)
        if not path_key and cat in INSPECT_CATS:
            path_key = normalize_path(command[:240])
        actions.append(
            {
                "ts": ts,
                "tokens": tokens_at(calls, ts),
                "cat": cat,
                "tool": tool,
                "command": command,
                "path": path,
                "path_key": path_key,
                "summary": summary,
                "cmd_hash": cmd_h,
                "out_hash": out_h,
                "pair_hash": pair_hash(cmd_h, out_h) if cmd_h or out_h else "",
                "exit_code": exit_code,
            }
        )

    for event in iter_jsonl(events_path):
        kind = event.get("kind")
        if kind == "ActionEvent":
            if pending is not None:
                flush(pending, None)
            pending = event
            continue
        if kind == "ObservationEvent":
            if pending is not None:
                flush(pending, event)
                pending = None
    if pending is not None:
        flush(pending, None)
    return calls, actions


def annotate_novelty(actions: list[dict[str, Any]]) -> None:
    seen_cmd: set[str] = set()
    seen_out: set[str] = set()
    seen_pair: set[str] = set()
    seen_path: set[str] = set()
    for action in actions:
        cmd_h = action.get("cmd_hash") or ""
        out_h = action.get("out_hash") or ""
        pair = action.get("pair_hash") or ""
        path_key = action.get("path_key") or ""
        action["cmd_novel"] = bool(cmd_h) and cmd_h not in seen_cmd
        action["out_novel"] = bool(out_h) and out_h not in seen_out
        action["pair_novel"] = bool(pair) and pair not in seen_pair
        action["path_novel"] = bool(path_key) and path_key not in seen_path
        action["identical_rerun"] = bool(pair) and pair in seen_pair
        if cmd_h:
            seen_cmd.add(cmd_h)
        if out_h:
            seen_out.add(out_h)
        if pair:
            seen_pair.add(pair)
        if path_key:
            seen_path.add(path_key)


def _trees_at_or_before(unique: list[dict[str, Any]], tokens: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in unique:
        tree_tokens = item.get("tokens")
        if tree_tokens is None:
            continue
        if int(tree_tokens) <= int(tokens):
            out.append(item)
    return out


def _next_tree_after(unique: list[dict[str, Any]], tokens: int) -> dict[str, Any] | None:
    later = []
    for item in unique:
        tree_tokens = item.get("tokens")
        if tree_tokens is None:
            continue
        if int(tree_tokens) > int(tokens):
            later.append(item)
    return later[0] if later else None


def current_tree_hash(unique: list[dict[str, Any]], tokens: int) -> str | None:
    trees = _trees_at_or_before(unique, tokens)
    if not trees:
        return None
    return str(trees[-1].get("tree_hash") or "") or None


def features_from_history(
    actions: list[dict[str, Any]],
    index: int,
    *,
    unique: list[dict[str, Any]] | None = None,
    window_k: int = WINDOW_K,
) -> dict[str, float]:
    """Causal features at actions[index]. Does not take T*."""
    current = actions[index]
    history = actions[: index + 1]
    tokens = int(current.get("tokens") or 0)
    unique = unique or []

    streak = 0
    for item in reversed(history):
        if item.get("cat") == "self_test_run":
            streak += 1
            continue
        break

    window = history[-window_k:]
    self_tests = [item for item in window if item.get("cat") == "self_test_run"]
    out_novel_frac = (
        sum(1 for item in self_tests if item.get("out_novel")) / len(self_tests)
        if self_tests
        else 0.0
    )

    cmd_items = [item for item in window if item.get("cmd_hash")]
    repeat_cmd = (
        sum(1 for item in cmd_items if not item.get("cmd_novel")) / len(cmd_items)
        if cmd_items
        else 0.0
    )
    read_items = [item for item in window if item.get("cat") in INSPECT_CATS]
    repeat_read = (
        sum(1 for item in read_items if not item.get("path_novel")) / len(read_items)
        if read_items
        else 0.0
    )

    trees = _trees_at_or_before(unique, tokens)
    last_write_tokens = int(trees[-1]["tokens"]) if trees else None
    if last_write_tokens is None:
        tokens_since = 0.0
        steps_since = 0.0
    else:
        tokens_since = float(max(0, tokens - last_write_tokens))
        steps_since = float(
            sum(1 for item in history if int(item.get("tokens") or 0) > last_write_tokens)
        )

    trees_now = len(trees)
    window_start_tokens = int(window[0].get("tokens") or 0) if window else 0
    trees_window_start = len(_trees_at_or_before(unique, window_start_tokens))
    recent_new_trees = float(max(0, trees_now - trees_window_start))
    last_bytes = float(trees[-1].get("n_bytes") or 0) if trees else 0.0

    is_self_test = current.get("cat") == "self_test_run"
    features = {
        "consecutive_self_tests": float(streak),
        "self_test_cmd_novel": float(bool(is_self_test and current.get("cmd_novel"))),
        "self_test_out_novel": float(bool(is_self_test and current.get("out_novel"))),
        "self_test_pair_novel": float(bool(is_self_test and current.get("pair_novel"))),
        "frac_recent_self_test_out_novel": float(out_novel_frac),
        "tokens_since_last_useful_write": tokens_since,
        "steps_since_last_useful_write": steps_since,
        "repeat_command_rate": float(repeat_cmd),
        "repeat_read_rate": float(repeat_read),
        "unique_trees_so_far": float(trees_now),
        "recent_new_trees": recent_new_trees,
        "last_tree_n_bytes": last_bytes,
    }
    assert_legal_features(features)
    return features


def attach_action_features(
    actions: list[dict[str, Any]],
    *,
    unique: list[dict[str, Any]] | None = None,
    window_k: int = WINDOW_K,
) -> None:
    annotate_novelty(actions)
    for index in range(len(actions)):
        actions[index]["features"] = features_from_history(
            actions, index, unique=unique, window_k=window_k
        )


def followed_by_package_write(actions: list[dict[str, Any]], index: int, lookahead: int = LOOKAHEAD_ACTIONS) -> bool:
    end = min(len(actions), index + 1 + lookahead)
    for item in actions[index + 1 : end]:
        if item.get("cat") == "package_write":
            return True
    return False


def classify_self_test_event(
    action: dict[str, Any],
    *,
    t_star: int,
    unique: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    index: int,
) -> dict[str, Any]:
    tokens = int(action.get("tokens") or 0)
    before = tokens < int(t_star)
    current_hash = current_tree_hash(unique, tokens)
    nxt = _next_tree_after(unique, tokens)
    new_tree = bool(
        nxt
        and nxt.get("tree_hash")
        and nxt.get("tree_hash") != current_hash
    )
    tree_tokens = int(nxt.get("tokens") or 0) if nxt else None
    new_tree_soon = bool(
        new_tree
        and tree_tokens is not None
        and 0 < tree_tokens - tokens <= NEW_TREE_SOON_TOKENS
    )
    new_tree_before_tstar = bool(
        new_tree
        and tree_tokens is not None
        and tree_tokens <= int(t_star)
        and 0 < tree_tokens - tokens <= NEW_TREE_SOON_TOKENS
    )
    patch_soon = followed_by_package_write(actions, index)
    new_info = bool(action.get("out_novel") or action.get("cmd_novel"))
    identical = bool(action.get("identical_rerun"))
    useful_strict = bool(before and new_info and patch_soon)
    useful_loose = bool(before and new_tree_before_tstar)
    return {
        "tokens": tokens,
        "before_tstar": before,
        "cmd_novel": bool(action.get("cmd_novel")),
        "out_novel": bool(action.get("out_novel")),
        "pair_novel": bool(action.get("pair_novel")),
        "identical_rerun": identical,
        "new_info": new_info,
        "followed_by_package_write": patch_soon,
        "followed_by_new_tree": new_tree,
        "followed_by_new_tree_soon": new_tree_soon,
        "followed_by_new_tree_before_tstar": new_tree_before_tstar,
        "useful_strict": useful_strict,
        "useful_loose": useful_loose,
    }


def roc_auc(labels: list[int], scores: list[float]) -> float | None:
    """Mann-Whitney AUC with average ranks for ties. None if one class missing."""
    pairs = [
        (float(score), int(label))
        for score, label in zip(scores, labels)
        if score is not None and not math.isnan(float(score))
    ]
    n_pos = sum(label for _score, label in pairs)
    n_neg = len(pairs) - n_pos
    if n_pos <= 0 or n_neg <= 0:
        return None
    ordered = sorted(range(len(pairs)), key=lambda i: pairs[i][0])
    ranks = [0.0] * len(pairs)
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and pairs[ordered[j + 1]][0] == pairs[ordered[i]][0]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[ordered[k]] = avg_rank
        i = j + 1
    rank_sum_pos = sum(ranks[i] for i, (_score, label) in enumerate(pairs) if label == 1)
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    mean = sum(values) / len(values)
    var = sum((value - mean) ** 2 for value in values) / len(values)
    std = math.sqrt(var) if var > 0 else 1.0
    return [(value - mean) / std for value in values]


def hypothesized_already_enough_score(features: dict[str, float]) -> float:
    """Unfitted linear combo. Higher => guess already enough. Not a stop rule."""
    return (
        features["consecutive_self_tests"]
        + math.log1p(features["tokens_since_last_useful_write"])
        + features["steps_since_last_useful_write"]
        + 4.0 * features["repeat_command_rate"]
        + 4.0 * features["repeat_read_rate"]
        - 4.0 * features["frac_recent_self_test_out_novel"]
        - 4.0 * features["self_test_out_novel"]
        - 2.0 * features["recent_new_trees"]
    )


def mean_or_none(values: Iterable[float]) -> float | None:
    seq = [float(value) for value in values]
    if not seq:
        return None
    return sum(seq) / len(seq)


def rate_or_none(flags: Iterable[bool]) -> float | None:
    seq = list(flags)
    if not seq:
        return None
    return sum(1 for item in seq if item) / len(seq)


def attribute_tokens(
    calls: list[tuple[float, int, int]],
    actions: list[dict[str, Any]],
) -> None:
    for action in actions:
        action["billed"] = 0
    if not calls or not actions:
        return
    for i, (ts, billed, _cum) in enumerate(calls):
        nxt = next((a for a in actions if a["ts"] is not None and a["ts"] >= ts - 0.05), None)
        if nxt is None:
            actions[-1]["billed"] += billed
        else:
            nxt["billed"] += billed
