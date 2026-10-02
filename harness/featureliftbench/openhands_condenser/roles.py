"""SDK-free observation-role rules for FeatureLiftBench condensers.

Persistent information cannot be evicted, but this module never re-injects a
full working tree on every step. Ephemeral re-reads keep a short stub so the
model still sees that it revisited the file.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from dataclasses import replace
from typing import Any
from typing import Iterable
from typing import Mapping


ROLE_PERSISTENT = "persistent"
ROLE_EPHEMERAL = "ephemeral"
ROLE_STRUCTURAL = "structural"

RECENCY_MASKING = "recency_masking"
ARTIFACT_AWARE = "artifact_aware"

DEFAULT_ATTENTION_WINDOW = 100
CHARS_PER_TOKEN = 4

SPEC_BASENAMES = frozenset(
    {
        "task.md",
        "public_contract.json",
        "public_spec.json",
        "metadata.json",
        "openhands_task.md",
    }
)
SPEC_DIR_MARKERS = ("/public_spec/", "/public_contract/")
ARTIFACT_DIR_MARKERS = ("/submission/", "/featurelifted/")
WORKSPACE_PREFIXES = (
    "/flb/workspace/",
    "/workspace/",
)

READ_COMMANDS = frozenset(
    {"cat", "head", "tail", "less", "more", "nl", "bat", "sed", "awk"}
)
WRITE_COMMANDS = frozenset({"tee", "cp", "mv", "install"})
RE_READ_STUB = "Re-read unchanged file: {path}"
RE_RAN_STUB = "Re-ran unchanged command"
RECENCY_STUB = "Observation omitted (outside attention window)"
TOKEN_STUB = "Ephemeral observation omitted (token budget)"
UPDATED_STUB = "Superseded file contents: {path}"

_PATH_TOKEN_RE = re.compile(r"(?:(?:\./|/)?[\w.+@-]+(?:/[\w.+@-]+)+|\./[\w.+@-]+)")
_REDIRECT_RE = re.compile(r"(?:>>?|tee(?:\s+-a)?)\s+([^\s;&|]+)")
_FLAG_RE = re.compile(r"^-[A-Za-z0-9-]+$")


@dataclass(frozen=True)
class CondenserEvent:
    """Normalized event used by SDK-free condenser rules."""

    source: str
    is_observation: bool
    body: str
    path: str | None = None
    command: str | None = None
    is_write: bool = False
    kind: str = ""
    exit_code: int | None = None
    tool_name: str = ""


@dataclass(frozen=True)
class CondenseStats:
    kept_full: int = 0
    re_read_stubs: int = 0
    recency_masked: int = 0
    token_masked: int = 0
    persistent_protected: int = 0
    superseded_artifact: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "kept_full": self.kept_full,
            "re_read_stubs": self.re_read_stubs,
            "recency_masked": self.recency_masked,
            "token_masked": self.token_masked,
            "persistent_protected": self.persistent_protected,
            "superseded_artifact": self.superseded_artifact,
        }


def event_from_mapping(payload: Mapping[str, Any]) -> CondenserEvent:
    """Build a normalized event from an OpenHands-like mapping."""

    source = str(payload.get("source") or "").strip().lower()
    kind = str(payload.get("kind") or payload.get("type") or "")
    observation = payload.get("observation")
    action = payload.get("action")
    is_observation = bool(observation) or "observation" in kind.lower()
    command = _command_from_payload(payload)
    path = _path_from_payload(payload, command)
    body = _body_from_payload(payload)
    is_write = _is_write_payload(payload, command, path)
    exit_code = _exit_code_from_payload(payload)
    tool_name = str(payload.get("tool_name") or "").strip()
    if not is_observation and source == "environment" and body:
        is_observation = True
    return CondenserEvent(
        source=source,
        is_observation=is_observation,
        body=body,
        path=path,
        command=command,
        is_write=is_write,
        kind=kind,
        exit_code=exit_code,
        tool_name=tool_name,
    )


def apply_recency_masking(
    events: Iterable[CondenserEvent],
    *,
    attention_window: int = DEFAULT_ATTENTION_WINDOW,
) -> tuple[list[CondenserEvent], CondenseStats]:
    """Keep recent observation bodies; stub older observation bodies."""

    items = list(events)
    window = max(1, int(attention_window))
    cutoff = max(0, len(items) - window)
    out: list[CondenserEvent] = []
    stats = CondenseStats()
    for index, event in enumerate(items):
        if not event.is_observation:
            out.append(event)
            continue
        if index >= cutoff:
            out.append(event)
            stats = replace(stats, kept_full=stats.kept_full + 1)
            continue
        out.append(replace(event, body=RECENCY_STUB))
        stats = replace(stats, recency_masked=stats.recency_masked + 1)
    return out, stats


def apply_artifact_aware(
    events: Iterable[CondenserEvent],
    *,
    trigger_tokens: int | None = None,
) -> tuple[list[CondenserEvent], CondenseStats]:
    """Retain persistent latest state; stub unchanged ephemeral re-reads."""

    items = list(events)
    written_paths = {event.path for event in items if event.path and event.is_write}
    last_artifact_index = _last_observation_index_by_path(
        items,
        {
            path
            for path in written_paths
            if path is not None and _looks_like_artifact_path(path)
        },
    )
    roles = [
        _role_for(event, index, last_artifact_index)
        for index, event in enumerate(items)
    ]
    out = list(items)
    stats = CondenseStats()
    seen_hashes: dict[str, str] = {}

    for index, event in enumerate(items):
        if not event.is_observation:
            continue
        if (
            event.path
            and event.path in last_artifact_index
            and last_artifact_index[event.path] != index
        ):
            out[index] = replace(event, body=UPDATED_STUB.format(path=event.path))
            stats = replace(stats, superseded_artifact=stats.superseded_artifact + 1)
            continue
        if roles[index] == ROLE_PERSISTENT:
            stats = replace(stats, persistent_protected=stats.persistent_protected + 1)
            continue

        key = _evidence_key(event)
        digest = _body_hash(event.body)
        previous = seen_hashes.get(key)
        if previous is None:
            seen_hashes[key] = digest
            stats = replace(stats, kept_full=stats.kept_full + 1)
            continue
        if previous == digest:
            stub = RE_READ_STUB.format(path=event.path) if event.path else RE_RAN_STUB
            out[index] = replace(event, body=stub)
            stats = replace(stats, re_read_stubs=stats.re_read_stubs + 1)
            continue
        seen_hashes[key] = digest
        stats = replace(stats, kept_full=stats.kept_full + 1)

    if trigger_tokens:
        out, extra_masked = _mask_oldest_ephemeral(
            out,
            roles,
            trigger_chars=max(1, int(trigger_tokens) * CHARS_PER_TOKEN),
        )
        stats = replace(stats, token_masked=stats.token_masked + extra_masked)
    return out, stats


def _role_for(
    event: CondenserEvent,
    index: int,
    last_artifact_index: dict[str, int],
) -> str:
    if not event.is_observation:
        if event.source == "user":
            return ROLE_PERSISTENT
        return ROLE_STRUCTURAL
    if event.source == "user":
        return ROLE_PERSISTENT
    if event.path and _looks_like_spec_path(event.path):
        return ROLE_PERSISTENT
    if event.path and last_artifact_index.get(event.path) == index:
        return ROLE_PERSISTENT
    return ROLE_EPHEMERAL


def _last_observation_index_by_path(
    events: list[CondenserEvent],
    paths: set[str],
) -> dict[str, int]:
    latest: dict[str, int] = {}
    for index, event in enumerate(events):
        if event.is_observation and event.path in paths:
            latest[event.path] = index
    return latest


def _mask_oldest_ephemeral(
    events: list[CondenserEvent],
    roles: list[str],
    *,
    trigger_chars: int,
) -> tuple[list[CondenserEvent], int]:
    total = sum(len(event.body) for event in events)
    if total <= trigger_chars:
        return events, 0
    out = list(events)
    masked = 0
    for index, event in enumerate(out):
        if total <= trigger_chars:
            break
        if roles[index] != ROLE_EPHEMERAL or not event.is_observation:
            continue
        if event.body in {RECENCY_STUB, TOKEN_STUB}:
            continue
        reduction = max(0, len(event.body) - len(TOKEN_STUB))
        out[index] = replace(event, body=TOKEN_STUB)
        total -= reduction
        masked += 1
    return out, masked


def _evidence_key(event: CondenserEvent) -> str:
    if event.path:
        return f"path:{event.path}"
    command = (event.command or "").strip()
    if command:
        return f"cmd:{command}"
    return f"body:{_body_hash(event.body)}"


def _body_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()


def _looks_like_spec_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    basename = lowered.rsplit("/", 1)[-1]
    if basename in SPEC_BASENAMES:
        return True
    return any(marker in lowered for marker in SPEC_DIR_MARKERS)


def _looks_like_artifact_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    return any(marker in lowered for marker in ARTIFACT_DIR_MARKERS)


def _command_from_payload(payload: Mapping[str, Any]) -> str | None:
    action = payload.get("action")
    if isinstance(action, Mapping):
        command = action.get("command")
        if isinstance(command, str) and command.strip():
            return command.strip()
        path = action.get("path")
        if isinstance(path, str) and path.strip():
            return f"edit {path.strip()}"
    observation = payload.get("observation")
    if isinstance(observation, Mapping):
        command = observation.get("command")
        if isinstance(command, str) and command.strip():
            return command.strip()
    tool_name = payload.get("tool_name")
    if tool_name == "terminal":
        tool_call = payload.get("tool_call")
        if isinstance(tool_call, Mapping):
            arguments = tool_call.get("arguments")
            if isinstance(arguments, str) and "command" in arguments:
                return None
            if isinstance(arguments, Mapping):
                command = arguments.get("command")
                if isinstance(command, str) and command.strip():
                    return command.strip()
    return None


def _path_from_payload(payload: Mapping[str, Any], command: str | None) -> str | None:
    for key in ("path", "file_path", "filepath"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return _normalize_path(value)
    action = payload.get("action")
    if isinstance(action, Mapping):
        for key in ("path", "file_path", "filepath"):
            value = action.get(key)
            if isinstance(value, str) and value.strip():
                return _normalize_path(value)
    observation = payload.get("observation")
    if isinstance(observation, Mapping):
        for key in ("path", "file_path", "filepath"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                return _normalize_path(value)
    if command:
        redirect = _REDIRECT_RE.search(command)
        if redirect:
            return _normalize_path(redirect.group(1))
        tokens = command.split()
        if tokens:
            verb = tokens[0].rsplit("/", 1)[-1]
            if verb in READ_COMMANDS or verb in {"cp", "mv", "tee"}:
                for token in tokens[1:]:
                    if _FLAG_RE.match(token) or token in {">", ">>", "|", "&&"}:
                        continue
                    if "/" in token or token.endswith((".py", ".md", ".json", ".txt")):
                        return _normalize_path(token)
    return None


def _body_from_payload(payload: Mapping[str, Any]) -> str:
    observation = payload.get("observation")
    if isinstance(observation, str):
        return observation
    if isinstance(observation, Mapping):
        content = observation.get("content")
        extracted = _text_from_content(content)
        if extracted:
            return extracted
    message = payload.get("llm_message")
    if isinstance(message, Mapping):
        extracted = _text_from_content(message.get("content"))
        if extracted:
            return extracted
    for key in ("content", "message", "thought"):
        extracted = _text_from_content(payload.get(key))
        if extracted:
            return extracted
    return ""


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _is_write_payload(
    payload: Mapping[str, Any],
    command: str | None,
    path: str | None,
) -> bool:
    kind = str(payload.get("kind") or "")
    tool_name = str(payload.get("tool_name") or "")
    if "edit" in kind.lower() or "write" in kind.lower():
        return True
    if tool_name in {"file_editor", "str_replace_editor", "edit_file"}:
        return True
    action = payload.get("action")
    if isinstance(action, Mapping):
        action_kind = str(action.get("kind") or "")
        if "edit" in action_kind.lower() or "write" in action_kind.lower():
            return True
    if not command:
        return False
    if _REDIRECT_RE.search(command):
        return True
    verb = command.split()[0].rsplit("/", 1)[-1]
    if verb in {"cp", "mv", "tee", "install"}:
        return bool(path and _looks_like_artifact_path(path))
    return False


def _normalize_path(raw: str) -> str:
    path = raw.strip().strip("\"'")
    for prefix in WORKSPACE_PREFIXES:
        if path.startswith(prefix):
            path = path[len(prefix) :]
            break
    if path.startswith("./"):
        path = path[2:]
    return path


def _exit_code_from_payload(payload: Mapping[str, Any]) -> int | None:
    observation = payload.get("observation")
    if isinstance(observation, Mapping) and "exit_code" in observation:
        raw = observation.get("exit_code")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None
    if "exit_code" in payload:
        raw = payload.get("exit_code")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None
    return None
