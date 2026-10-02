"""Local OpenAI-compatible usage audit proxy for OpenHands runs."""

from __future__ import annotations

import gzip
import json
import re
import threading
import time
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

from .openhands_usage import context_policy_audit_fields
from .openhands_usage import openhands_context_limits


PROXY_DISABLE_ENV = "FEATURELIFTBENCH_OPENHANDS_USAGE_PROXY"
TOTAL_TOKEN_LIMIT_ENV = "FEATURELIFTBENCH_OPENHANDS_TOTAL_TOKEN_LIMIT"
TOOL_ALIAS_COMPAT_ENV = "FEATURELIFTBENCH_OPENHANDS_TOOL_ALIAS_COMPAT"
STREAM_INCLUDE_USAGE_ENV = "FEATURELIFTBENCH_OPENHANDS_STREAM_INCLUDE_USAGE"
_VERSIONED_API_PATH = re.compile(r"/v\d+$")


@dataclass(frozen=True)
class LLMUsageProxyConfig:
    target_base_url: str
    api_key: str
    audit_path: Path
    usage_path: Path
    model: str = ""
    total_token_limit: int | None = None
    tool_alias_compat: bool = False
    inject_stream_include_usage: bool = True
    strip_usage_only_sse: bool = True


class LLMUsageProxy:
    """Forward OpenAI-compatible requests while auditing provider usage fields."""

    def __init__(self, config: LLMUsageProxyConfig) -> None:
        self.config = config
        self._server: _ProxyServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._api_calls = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._prompt_cache_hit_tokens = 0
        self._prompt_cache_miss_tokens = 0
        self._saw_prompt_cache_usage = False
        self._max_prompt_tokens_per_call = 0
        self._max_total_tokens_per_call = 0
        self._saw_verified_usage = False
        self._context_violation = False
        self._token_budget_exhausted = False
        self._budget_rejections = 0
        self._tool_alias_normalizations = 0

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("proxy has not been started")
        host, port = self._server.server_address
        return f"http://{host}:{port}/v1"

    def start(self) -> "LLMUsageProxy":
        self.config.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.usage_path.parent.mkdir(parents=True, exist_ok=True)
        self._server = _ProxyServer(("127.0.0.1", 0), _ProxyHandler, self)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def close(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        self.write_usage_summary()

    def __enter__(self) -> "LLMUsageProxy":
        return self.start()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def forward(self, handler: BaseHTTPRequestHandler) -> None:
        if self._token_limit_reached():
            self._reject_for_token_budget(handler)
            return
        content_length = _safe_int(handler.headers.get("Content-Length"))
        body = handler.rfile.read(content_length if content_length is not None else 0)
        request_payload = _json_object(body)
        injected_include_usage = False
        if self.config.inject_stream_include_usage:
            body, request_payload, injected_include_usage = _ensure_stream_include_usage(
                body,
                request_payload,
                path=handler.path,
            )
        target_url = self._target_url(handler.path)
        request = urllib.request.Request(
            target_url,
            data=body,
            headers=self._forward_headers(handler),
            method=handler.command,
        )
        status = 502
        response_headers: dict[str, str] = {"Content-Type": "application/json"}
        response_body = json.dumps(
            {"error": {"message": "proxy forwarding failed"}},
            sort_keys=True,
        ).encode("utf-8")
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                status = int(response.status)
                response_body = response.read()
                response_headers = _response_headers(response.headers)
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            response_body = exc.read()
            response_headers = _response_headers(exc.headers)
        except urllib.error.URLError as exc:
            response_body = json.dumps(
                {"error": {"message": str(exc.reason)}},
                sort_keys=True,
            ).encode("utf-8")

        alias_normalizations = 0
        decoded_body = _decode_http_body(response_body, response_headers)
        if self.config.tool_alias_compat and status < 400:
            decoded_body, alias_normalizations = _normalize_tool_argument_aliases(
                decoded_body
            )
            if decoded_body != response_body and not _content_encoding(response_headers):
                response_body = decoded_body

        self._record_call(
            path=handler.path,
            target_url=target_url,
            status=status,
            request_payload=request_payload,
            response_body=decoded_body,
            response_headers=response_headers,
            alias_normalizations=alias_normalizations,
            stream_include_usage_injected=injected_include_usage,
        )
        if self.config.strip_usage_only_sse:
            stripped = _strip_usage_only_sse(decoded_body)
            if stripped != decoded_body and not _content_encoding(response_headers):
                response_body = stripped
        handler.send_response(status)
        for key, value in response_headers.items():
            if key.lower() in {"connection", "content-length", "transfer-encoding"}:
                continue
            handler.send_header(key, value)
        handler.send_header("Content-Length", str(len(response_body)))
        handler.end_headers()
        handler.wfile.write(response_body)

    def write_usage_summary(self) -> None:
        limits = openhands_context_limits()
        with self._lock:
            api_calls = self._api_calls
            if api_calls <= 0:
                return
            prompt_tokens = self._prompt_tokens
            completion_tokens = self._completion_tokens
            cache_hit_tokens = self._prompt_cache_hit_tokens
            cache_miss_tokens = self._prompt_cache_miss_tokens
            saw_cache_usage = self._saw_prompt_cache_usage
            max_prompt = self._max_prompt_tokens_per_call
            max_total = self._max_total_tokens_per_call
            saw_verified = self._saw_verified_usage
            context_violation = self._context_violation
            token_budget_exhausted = self._token_budget_exhausted
            budget_rejections = self._budget_rejections
            tool_alias_normalizations = self._tool_alias_normalizations

        token_source = "openhands_proxy" if saw_verified else "openhands_proxy_no_provider_usage"
        usage = {
            "assistant_steps": 0,
            "api_calls": api_calls,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "prompt_cache_accounting_available": saw_cache_usage,
            "prompt_cache_hit_tokens": cache_hit_tokens,
            "prompt_cache_miss_tokens": cache_miss_tokens,
            "prompt_cache_hit_rate": (
                cache_hit_tokens / (cache_hit_tokens + cache_miss_tokens)
                if saw_cache_usage and cache_hit_tokens + cache_miss_tokens > 0
                else None
            ),
            "effective_uncached_prompt_tokens": (
                cache_miss_tokens if saw_cache_usage else None
            ),
            "total_token_limit": self.config.total_token_limit,
            "token_budget_exhausted": token_budget_exhausted,
            "budget_rejections": budget_rejections,
            "tool_alias_compat": self.config.tool_alias_compat,
            "tool_alias_normalizations": tool_alias_normalizations,
            "context_audit": {
                "available": saw_verified,
                "runtime": "openhands",
                "history_policy": "external_openhands",
                "token_source": token_source,
                "usage_unverified": not saw_verified,
                "context_window_tokens": limits.context_window_tokens,
                "reserved_output_tokens": limits.reserved_output_tokens,
                "max_allowed_prompt_tokens": limits.max_allowed_prompt_tokens,
                "max_prompt_tokens_per_call": max_prompt,
                "max_total_tokens_per_call": max_total,
                "context_violation": context_violation,
                "over_context_behavior": "audited_by_featureliftbench_proxy",
                **context_policy_audit_fields(),
                "condensation_events": 0,
                "forgotten_event_count": 0,
                "condensation_summaries_nonempty": 0,
            },
        }
        self.config.usage_path.write_text(
            json.dumps(usage, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _target_url(self, request_path: str) -> str:
        base = self.config.target_base_url.rstrip("/")
        parsed = urlsplit(base)
        base_path = parsed.path.rstrip("/")
        path = request_path
        # LiteLLM talks to the proxy as OpenAI (/v1/...). If the provider base
        # already has a version suffix (/v1, /v4, ...), drop the extra /v1.
        if _VERSIONED_API_PATH.search(base_path) and path.startswith("/v1/"):
            path = path[len("/v1") :]
        if not path.startswith("/"):
            path = "/" + path
        return urlunsplit((parsed.scheme, parsed.netloc, base_path + path, "", ""))

    def _forward_headers(self, handler: BaseHTTPRequestHandler) -> dict[str, str]:
        headers: dict[str, str] = {}
        for key, value in handler.headers.items():
            if key.lower() in {"host", "content-length", "connection", "authorization"}:
                continue
            headers[key] = value
        headers.setdefault("Content-Type", "application/json")
        headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _record_call(
        self,
        *,
        path: str,
        target_url: str,
        status: int,
        request_payload: dict[str, Any] | None,
        response_body: bytes,
        response_headers: dict[str, str] | None = None,
        alias_normalizations: int = 0,
        stream_include_usage_injected: bool = False,
    ) -> None:
        usage, usage_parse = _extract_provider_usage(response_body)
        prompt = _int_metric(usage.get("prompt_tokens"))
        if prompt is None:
            prompt = _int_metric(usage.get("input_tokens"))
        completion = _int_metric(usage.get("completion_tokens"))
        if completion is None:
            completion = _int_metric(usage.get("output_tokens"))
        cache_hit, cache_miss, cache_available = _prompt_cache_metrics(
            usage,
            prompt_tokens=prompt,
        )
        total = _int_metric(usage.get("total_tokens"))
        if total is None and (prompt is not None or completion is not None):
            total = (prompt or 0) + (completion or 0)
        model = ""
        if isinstance(request_payload, dict) and isinstance(request_payload.get("model"), str):
            model = request_payload["model"]
        elif self.config.model:
            model = self.config.model

        verified = prompt is not None
        prompt_value = prompt or 0
        completion_value = completion or 0
        total_value = total or (prompt_value + completion_value)
        limits = openhands_context_limits()
        context_violation = verified and prompt_value > limits.max_allowed_prompt_tokens
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "runtime": "openhands",
            "phase": "openhands_proxy",
            "path": path,
            "target_url": _redact_url(target_url),
            "status": status,
            "model": model,
            "usage_verified": verified,
            "usage_parse": usage_parse,
            "stream_include_usage_injected": stream_include_usage_injected,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            "prompt_cache_accounting_available": cache_available,
            "prompt_cache_hit_tokens": cache_hit,
            "prompt_cache_miss_tokens": cache_miss,
            "context_window_tokens": limits.context_window_tokens,
            "max_allowed_prompt_tokens": limits.max_allowed_prompt_tokens,
            "context_violation": context_violation,
            "tool_alias_normalizations": alias_normalizations,
            **_wire_debug(
                response_body,
                request_payload,
                response_headers or {},
            ),
        }
        with self._lock:
            self._api_calls += 1
            self._prompt_tokens += prompt_value
            self._completion_tokens += completion_value
            self._prompt_cache_hit_tokens += cache_hit or 0
            self._prompt_cache_miss_tokens += cache_miss or 0
            self._saw_prompt_cache_usage = (
                self._saw_prompt_cache_usage or cache_available
            )
            self._max_prompt_tokens_per_call = max(
                self._max_prompt_tokens_per_call,
                prompt_value,
            )
            self._max_total_tokens_per_call = max(
                self._max_total_tokens_per_call,
                total_value,
            )
            self._saw_verified_usage = self._saw_verified_usage or verified
            self._context_violation = self._context_violation or bool(context_violation)
            self._tool_alias_normalizations += alias_normalizations
            if (
                self.config.total_token_limit is not None
                and self._prompt_tokens + self._completion_tokens >= self.config.total_token_limit
            ):
                self._token_budget_exhausted = True
            with self.config.audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")

    def _token_limit_reached(self) -> bool:
        limit = self.config.total_token_limit
        if limit is None:
            return False
        with self._lock:
            return self._prompt_tokens + self._completion_tokens >= limit

    def _reject_for_token_budget(self, handler: BaseHTTPRequestHandler) -> None:
        body = json.dumps(
            {
                "error": {
                    "code": "featureliftbench_token_budget_exhausted",
                    "message": (
                        "FeatureLiftBench per-instance token budget exhausted; "
                        "the experiment runner will not forward another model call"
                    ),
                }
            },
            sort_keys=True,
        ).encode("utf-8")
        with self._lock:
            self._token_budget_exhausted = True
            self._budget_rejections += 1
            record = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "runtime": "openhands",
                "phase": "token_budget_guard",
                "path": handler.path,
                "status": 400,
                "total_token_limit": self.config.total_token_limit,
                "tokens_observed": self._prompt_tokens + self._completion_tokens,
            }
            with self.config.audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        handler.send_response(400)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)


class _ProxyServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        proxy: LLMUsageProxy,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.proxy = proxy


class _ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        server = self.server
        if not isinstance(server, _ProxyServer):
            self.send_error(500)
            return
        server.proxy.forward(self)

    def log_message(self, format: str, *args: object) -> None:
        return


def maybe_start_openhands_usage_proxy(
    env: dict[str, str],
    agent_output_dir: Path,
) -> LLMUsageProxy | None:
    if env.get(PROXY_DISABLE_ENV, "").strip().lower() in {"0", "false", "no", "off"}:
        return None
    target_base_url = _first_non_empty(
        env.get("FEATURELIFTBENCH_API_BASE"),
        env.get("OPENAI_BASE_URL"),
        env.get("OPENAI_API_BASE"),
        env.get("LLM_BASE_URL"),
        env.get("DEEPSEEK_API_BASE"),
    )
    api_key = _first_non_empty(
        env.get("FEATURELIFTBENCH_API_KEY"),
        env.get("OPENAI_API_KEY"),
        env.get("LLM_API_KEY"),
        env.get("DEEPSEEK_API_KEY"),
    )
    if not target_base_url or not api_key:
        return None
    return LLMUsageProxy(
        LLMUsageProxyConfig(
            target_base_url=target_base_url,
            api_key=api_key,
            audit_path=agent_output_dir / "context_audit.jsonl",
            usage_path=agent_output_dir / "openhands_usage.json",
            model=env.get("LLM_MODEL") or env.get("FEATURELIFTBENCH_MODEL", ""),
            total_token_limit=_positive_int(env.get(TOTAL_TOKEN_LIMIT_ENV)),
            tool_alias_compat=_truthy(env.get(TOOL_ALIAS_COMPAT_ENV)),
            inject_stream_include_usage=_env_flag(
                env.get(STREAM_INCLUDE_USAGE_ENV),
                default=True,
            ),
        )
    )


def _normalize_tool_argument_aliases(response_body: bytes) -> tuple[bytes, int]:
    """Normalize known DeepSeek/vLLM tool-call schema mismatches for OpenHands.

    Transformations are deliberately narrow:
    - ``terminal``: rename ``security_rule`` -> ``security_risk`` when absent.
    - all tools: default ``security_risk`` to ``LOW`` when still absent.
    - ``think``: drop ``command``/``task_list`` extras that vLLM sometimes emits.
    """

    payload = _json_object(response_body)
    if payload is None:
        return response_body, 0
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return response_body, 0
    normalized = 0
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function = tool_call.get("function")
            if not isinstance(function, dict):
                continue
            tool_name = function.get("name")
            if not isinstance(tool_name, str):
                continue
            arguments = function.get("arguments")
            if not isinstance(arguments, str):
                continue
            try:
                parsed = json.loads(arguments)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue
            changed = False
            if tool_name == "terminal" and "security_risk" not in parsed and "security_rule" in parsed:
                parsed["security_risk"] = parsed.pop("security_rule")
                changed = True
            if tool_name == "think":
                for extra_key in ("command", "task_list"):
                    if extra_key in parsed:
                        parsed.pop(extra_key)
                        changed = True
            if "security_risk" not in parsed:
                parsed["security_risk"] = "LOW"
                changed = True
            if not changed:
                continue
            function["arguments"] = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
            normalized += 1
    if normalized == 0:
        return response_body, 0
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        normalized,
    )


def _response_headers(headers: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items():
        if isinstance(key, str) and isinstance(value, str):
            result[key] = value
    return result


def _content_encoding(headers: dict[str, str] | None) -> str:
    if not headers:
        return ""
    for key, value in headers.items():
        if key.lower() == "content-encoding":
            return value.lower().strip()
    return ""


def _decode_http_body(body: bytes, headers: dict[str, str] | None) -> bytes:
    """Inflate gzip/deflate provider bodies so usage JSON can be parsed."""

    encoding = _content_encoding(headers)
    sniffed_gzip = body.startswith(b"\x1f\x8b")
    if encoding in {"gzip", "x-gzip"} or (not encoding and sniffed_gzip):
        try:
            return gzip.decompress(body)
        except (OSError, EOFError):
            return body
    if encoding == "deflate":
        try:
            return zlib.decompress(body)
        except zlib.error:
            try:
                return zlib.decompress(body, -zlib.MAX_WBITS)
            except zlib.error:
                return body
    return body


def _json_object(data: bytes) -> dict[str, Any] | None:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _env_flag(value: str | None, *, default: bool) -> bool:
    if value is None or not str(value).strip():
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _is_streaming_request(payload: dict[str, Any]) -> bool:
    stream = payload.get("stream")
    return stream is True or stream == "true" or stream == 1


def _ensure_stream_include_usage(
    body: bytes,
    request_payload: dict[str, Any] | None,
    path: str = "",
) -> tuple[bytes, dict[str, Any] | None, bool]:
    """Ask chat-completions providers to emit a final SSE usage chunk.

    The OpenAI Responses API (``/v1/responses``) already puts usage on
    ``response.completed`` and rejects ``stream_options.include_usage``.
    """

    if _is_responses_path(path):
        return body, request_payload, False
    if not isinstance(request_payload, dict) or not _is_streaming_request(request_payload):
        return body, request_payload, False
    options = request_payload.get("stream_options")
    if isinstance(options, dict) and options.get("include_usage") is True:
        return body, request_payload, False
    updated = dict(request_payload)
    merged_options = dict(options) if isinstance(options, dict) else {}
    merged_options["include_usage"] = True
    updated["stream_options"] = merged_options
    return json.dumps(updated).encode("utf-8"), updated, True


def _is_responses_path(path: str) -> bool:
    stripped = (path or "").split("?", 1)[0].rstrip("/")
    return stripped.endswith("/responses")


def _looks_like_model_usage(usage: dict[str, Any]) -> bool:
    return any(
        _int_metric(usage.get(key)) is not None
        for key in (
            "input_tokens",
            "output_tokens",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        )
    )


def _walk_model_usage(payload: Any, *, depth: int = 0) -> dict[str, Any]:
    if depth > 6 or not isinstance(payload, dict):
        return {}
    last: dict[str, Any] = {}
    usage = payload.get("usage")
    if isinstance(usage, dict) and _looks_like_model_usage(usage):
        last = usage
    for key, value in payload.items():
        if key == "tool_usage":
            continue
        found = _walk_model_usage(value, depth=depth + 1)
        if found:
            last = found
    return last


def _usage_dict_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    candidates: list[Any] = [payload.get("usage")]
    nested = payload.get("response")
    if isinstance(nested, dict):
        candidates.append(nested.get("usage"))
    for usage in candidates:
        if isinstance(usage, dict) and _looks_like_model_usage(usage):
            return usage
    return _walk_model_usage(payload)


def _sse_event_data(event: str) -> str | None:
    chunks: list[str] = []
    for line in event.split("\n"):
        if line.startswith("data:"):
            chunks.append(line[5:].lstrip())
    if not chunks:
        return None
    return "\n".join(chunks)


def _is_usage_only_chunk(payload: dict[str, Any]) -> bool:
    usage = payload.get("usage")
    if not isinstance(usage, dict) or not usage:
        return False
    choices = payload.get("choices")
    return choices == [] or choices is None


def _extract_provider_usage(response_body: bytes) -> tuple[dict[str, Any], str]:
    payload = _json_object(response_body)
    if isinstance(payload, dict):
        usage = _usage_dict_from_payload(payload)
        if usage:
            return usage, "json"
        return {}, "none"
    try:
        text = response_body.decode("utf-8")
    except UnicodeDecodeError:
        return {}, "none"
    if "data:" not in text:
        return {}, "none"
    last: dict[str, Any] = {}
    for event in text.replace("\r\n", "\n").replace("\r", "\n").split("\n\n"):
        data = _sse_event_data(event)
        if not data or data == "[DONE]":
            continue
        try:
            obj = json.loads(data)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        usage = _usage_dict_from_payload(obj)
        if usage:
            last = usage
    if last:
        return last, "sse"
    # Concatenated JSON / messy SSE: scan every decodable object.
    try:
        text = response_body.decode("utf-8")
    except UnicodeDecodeError:
        return {}, "none"
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        if text.startswith("data:", idx) or text.startswith("event:", idx):
            newline = text.find("\n", idx)
            idx = len(text) if newline < 0 else newline + 1
            continue
        try:
            obj, end = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            idx += 1
            continue
        if isinstance(obj, dict):
            usage = _usage_dict_from_payload(obj)
            if usage:
                last = usage
        idx = end
    if last:
        return last, "sse"
    return {}, "none"


def _wire_debug(
    response_body: bytes,
    request_payload: dict[str, Any] | None,
    response_headers: dict[str, str],
) -> dict[str, Any]:
    content_type = ""
    for key, value in response_headers.items():
        if key.lower() == "content-type":
            content_type = value
            break
    head = response_body[:64].decode("utf-8", "replace").replace("\n", " | ")
    return {
        "response_bytes": len(response_body),
        "response_content_type": content_type.split(";")[0] if content_type else "",
        "response_head": head[:96],
        "has_response_completed": b"response.completed" in response_body,
        "has_input_tokens": b"input_tokens" in response_body,
        "has_prompt_tokens": b"prompt_tokens" in response_body,
        "content_encoding": _content_encoding(response_headers),
        "request_stream": (
            request_payload.get("stream") if isinstance(request_payload, dict) else None
        ),
        "request_keys": (
            sorted(request_payload.keys())[:24] if isinstance(request_payload, dict) else []
        ),
    }


def _strip_usage_only_sse(response_body: bytes) -> bytes:
    """Drop empty-choices usage chunks so OpenHands does not see include_usage."""

    try:
        text = response_body.decode("utf-8")
    except UnicodeDecodeError:
        return response_body
    stripped = text.lstrip()
    if not stripped.startswith("data:"):
        return response_body
    events = text.replace("\r\n", "\n").replace("\r", "\n").split("\n\n")
    kept: list[str] = []
    changed = False
    for event in events:
        if not event.strip():
            continue
        data = _sse_event_data(event)
        if data and data != "[DONE]":
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict) and _is_usage_only_chunk(obj):
                changed = True
                continue
        kept.append(event)
    if not changed:
        return response_body
    out = "\n\n".join(kept)
    if out and not out.endswith("\n\n"):
        out += "\n\n"
    return out.encode("utf-8")


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(value: str | None) -> int | None:
    parsed = _safe_int(value)
    return parsed if parsed is not None and parsed > 0 else None


def _int_metric(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value >= 0 and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


def _prompt_cache_metrics(
    usage: dict[str, Any],
    *,
    prompt_tokens: int | None,
) -> tuple[int | None, int | None, bool]:
    """Read DeepSeek/OpenAI-compatible cache accounting without inventing hits."""

    hit = _int_metric(usage.get("prompt_cache_hit_tokens"))
    miss = _int_metric(usage.get("prompt_cache_miss_tokens"))
    details = usage.get("prompt_tokens_details")
    if not isinstance(details, dict):
        details = usage.get("input_tokens_details")
    if hit is None and isinstance(details, dict):
        hit = _int_metric(details.get("cached_tokens"))
    available = hit is not None or miss is not None
    if available and hit is None:
        hit = 0
    if available and miss is None and prompt_tokens is not None:
        miss = max(0, prompt_tokens - (hit or 0))
    return hit, miss, available


def _first_non_empty(*values: str | None) -> str:
    for value in values:
        if value:
            return value
    return ""


def _redact_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
