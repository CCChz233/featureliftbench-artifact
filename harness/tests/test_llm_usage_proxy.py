from __future__ import annotations

import gzip
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from featureliftbench.llm_usage_proxy import LLMUsageProxy
from featureliftbench.llm_usage_proxy import LLMUsageProxyConfig
from featureliftbench.llm_usage_proxy import _ensure_stream_include_usage
from featureliftbench.llm_usage_proxy import _extract_provider_usage
from featureliftbench.llm_usage_proxy import _normalize_tool_argument_aliases
from featureliftbench.llm_usage_proxy import _strip_usage_only_sse
from featureliftbench.openhands_runner import OpenHandsRunnerConfig
from featureliftbench.openhands_runner import _write_usage


class LLMUsageProxyTests(unittest.TestCase):
    def test_tool_alias_compat_normalizes_terminal_security_field_and_defaults(self) -> None:
        body = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "terminal",
                                        "arguments": json.dumps(
                                            {
                                                "command": "pwd",
                                                "security_rule": "LOW",
                                            }
                                        ),
                                    }
                                },
                                {
                                    "function": {
                                        "name": "file_editor",
                                        "arguments": json.dumps(
                                            {
                                                "command": "create",
                                                "path": "/tmp/a.py",
                                            }
                                        ),
                                    }
                                },
                                {
                                    "function": {
                                        "name": "think",
                                        "arguments": json.dumps(
                                            {
                                                "thought": "plan work",
                                                "command": "plan",
                                                "task_list": [{"title": "step 1"}],
                                            }
                                        ),
                                    }
                                },
                            ]
                        }
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        ).encode("utf-8")

        normalized_body, count = _normalize_tool_argument_aliases(body)
        payload = json.loads(normalized_body)
        calls = payload["choices"][0]["message"]["tool_calls"]
        terminal_args = json.loads(calls[0]["function"]["arguments"])
        editor_args = json.loads(calls[1]["function"]["arguments"])
        think_args = json.loads(calls[2]["function"]["arguments"])

        self.assertEqual(count, 3)
        self.assertEqual(terminal_args["security_risk"], "LOW")
        self.assertNotIn("security_rule", terminal_args)
        self.assertEqual(editor_args["security_risk"], "LOW")
        self.assertEqual(think_args["security_risk"], "LOW")
        self.assertNotIn("command", think_args)
        self.assertNotIn("task_list", think_args)
        self.assertEqual(think_args["thought"], "plan work")

    def test_openhands_usage_artifact_preserves_cache_accounting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OpenHandsRunnerConfig(
                workspace_dir=root,
                task_file=root / "TASK.md",
                submission_dir=root / "submission",
                agent_output_dir=root,
                model="deepseek-v4-flash",
            )
            _write_usage(
                config,
                exit_status="passed",
                returncode=0,
                duration_seconds=1.0,
                raw_usage={
                    "prompt_tokens": 100,
                    "completion_tokens": 10,
                    "total_tokens": 110,
                    "prompt_cache_accounting_available": True,
                    "prompt_cache_hit_tokens": 80,
                    "prompt_cache_miss_tokens": 20,
                    "effective_uncached_prompt_tokens": 20,
                    "tool_alias_normalizations": 1,
                },
            )
            usage = json.loads((root / "usage.json").read_text(encoding="utf-8"))

        self.assertTrue(usage["prompt_cache_accounting_available"])
        self.assertEqual(usage["prompt_cache_hit_tokens"], 80)
        self.assertEqual(usage["prompt_cache_miss_tokens"], 20)
        self.assertEqual(usage["effective_uncached_prompt_tokens"], 20)
        self.assertEqual(usage["tool_alias_normalizations"], 1)

    def test_proxy_forwards_request_and_records_provider_usage(self) -> None:
        try:
            upstream = _FakeUpstreamServer()
        except PermissionError as exc:
            self.skipTest(f"local loopback sockets are unavailable: {exc}")
        upstream.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                proxy = LLMUsageProxy(
                    LLMUsageProxyConfig(
                        target_base_url=upstream.base_url + "/v1",
                        api_key="sk-real",
                        audit_path=root / "context_audit.jsonl",
                        usage_path=root / "openhands_usage.json",
                        model="deepseek-v4-flash",
                    )
                ).start()
                try:
                    body = json.dumps(
                        {
                            "model": "deepseek-v4-flash",
                            "messages": [{"role": "user", "content": "hello"}],
                        }
                    ).encode("utf-8")
                    request = urllib.request.Request(
                        proxy.base_url + "/chat/completions",
                        data=body,
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": "Bearer proxy-key",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=10) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                finally:
                    proxy.close()

                audit_records = [
                    json.loads(line)
                    for line in (root / "context_audit.jsonl").read_text(encoding="utf-8").splitlines()
                ]
                usage = json.loads((root / "openhands_usage.json").read_text(encoding="utf-8"))

            self.assertEqual(payload["usage"]["prompt_tokens"], 123)
            self.assertEqual(upstream.last_path, "/v1/chat/completions")
            self.assertEqual(upstream.last_authorization, "Bearer sk-real")
            self.assertEqual(len(audit_records), 1)
            self.assertTrue(audit_records[0]["usage_verified"])
            self.assertEqual(usage["api_calls"], 1)
            self.assertEqual(usage["prompt_tokens"], 123)
            self.assertEqual(usage["completion_tokens"], 45)
            self.assertTrue(usage["prompt_cache_accounting_available"])
            self.assertEqual(usage["prompt_cache_hit_tokens"], 100)
            self.assertEqual(usage["prompt_cache_miss_tokens"], 23)
            self.assertAlmostEqual(usage["prompt_cache_hit_rate"], 100 / 123)
            self.assertEqual(usage["effective_uncached_prompt_tokens"], 23)
            self.assertEqual(audit_records[0]["prompt_cache_hit_tokens"], 100)
            self.assertFalse(usage["context_audit"]["usage_unverified"])
            self.assertEqual(usage["context_audit"]["token_source"], "openhands_proxy")
            self.assertEqual(usage["context_audit"]["context_window_tokens"], 131072)
        finally:
            upstream.close()

    def test_proxy_uses_configured_context_window(self) -> None:
        try:
            upstream = _FakeUpstreamServer()
        except PermissionError as exc:
            self.skipTest(f"local loopback sockets are unavailable: {exc}")
        upstream.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with mock.patch.dict(
                    os.environ,
                    {
                        "FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS": "200",
                        "FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS": "50",
                    },
                    clear=False,
                ):
                    proxy = LLMUsageProxy(
                        LLMUsageProxyConfig(
                            target_base_url=upstream.base_url + "/v1",
                            api_key="sk-real",
                            audit_path=root / "context_audit.jsonl",
                            usage_path=root / "openhands_usage.json",
                            model="deepseek-v4-flash",
                        )
                    ).start()
                    try:
                        body = json.dumps(
                            {
                                "model": "deepseek-v4-flash",
                                "messages": [{"role": "user", "content": "hello"}],
                            }
                        ).encode("utf-8")
                        request = urllib.request.Request(
                            proxy.base_url + "/chat/completions",
                            data=body,
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        with urllib.request.urlopen(request, timeout=10) as response:
                            response.read()
                    finally:
                        proxy.close()

                usage = json.loads((root / "openhands_usage.json").read_text(encoding="utf-8"))

            self.assertEqual(usage["context_audit"]["context_window_tokens"], 200)
            self.assertEqual(usage["context_audit"]["reserved_output_tokens"], 50)
            self.assertEqual(usage["context_audit"]["max_allowed_prompt_tokens"], 150)
            self.assertFalse(usage["context_audit"]["context_violation"])
        finally:
            upstream.close()

    def test_proxy_stops_forwarding_after_total_token_budget(self) -> None:
        try:
            upstream = _FakeUpstreamServer()
        except PermissionError as exc:
            self.skipTest(f"local loopback sockets are unavailable: {exc}")
        upstream.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                proxy = LLMUsageProxy(
                    LLMUsageProxyConfig(
                        target_base_url=upstream.base_url + "/v1",
                        api_key="sk-real",
                        audit_path=root / "context_audit.jsonl",
                        usage_path=root / "openhands_usage.json",
                        model="deepseek-v4-flash",
                        total_token_limit=100,
                    )
                ).start()
                try:
                    body = json.dumps(
                        {"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": "hello"}]}
                    ).encode("utf-8")
                    first = urllib.request.Request(
                        proxy.base_url + "/chat/completions",
                        data=body,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(first, timeout=10) as response:
                        response.read()
                    second = urllib.request.Request(
                        proxy.base_url + "/chat/completions",
                        data=body,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(second, timeout=10)
                    self.assertEqual(caught.exception.code, 400)
                finally:
                    proxy.close()

                usage = json.loads((root / "openhands_usage.json").read_text(encoding="utf-8"))

            self.assertEqual(upstream.request_count, 1)
            self.assertTrue(usage["token_budget_exhausted"])
            self.assertEqual(usage["budget_rejections"], 1)
            self.assertEqual(usage["total_token_limit"], 100)
        finally:
            upstream.close()

    def test_proxy_strips_openai_v1_prefix_on_versioned_provider_bases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proxy = LLMUsageProxy(
                LLMUsageProxyConfig(
                    target_base_url="https://open.bigmodel.cn/api/paas/v4",
                    api_key="sk-test",
                    audit_path=root / "context_audit.jsonl",
                    usage_path=root / "openhands_usage.json",
                    model="openai/glm-5.3",
                )
            )
            self.assertEqual(
                proxy._target_url("/v1/chat/completions"),
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            )
            deepseek = LLMUsageProxy(
                LLMUsageProxyConfig(
                    target_base_url="https://api.deepseek.com/v1",
                    api_key="sk-test",
                    audit_path=root / "context_audit.jsonl",
                    usage_path=root / "openhands_usage.json",
                )
            )
            self.assertEqual(
                deepseek._target_url("/v1/chat/completions"),
                "https://api.deepseek.com/v1/chat/completions",
            )

    def test_extract_usage_from_sse_last_chunk(self) -> None:
        body = (
            'data: {"choices":[{"delta":{"content":"ok"}}],"usage":null}\n\n'
            'data: {"choices":[],"usage":{"prompt_tokens":13,"completion_tokens":4,"total_tokens":17}}\n\n'
            "data: [DONE]\n\n"
        ).encode("utf-8")
        usage, source = _extract_provider_usage(body)
        self.assertEqual(source, "sse")
        self.assertEqual(usage["prompt_tokens"], 13)
        self.assertEqual(usage["total_tokens"], 17)

    def test_strip_usage_only_sse_keeps_content_chunks(self) -> None:
        body = (
            'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
            'data: {"choices":[],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}\n\n'
            "data: [DONE]\n\n"
        ).encode("utf-8")
        stripped = _strip_usage_only_sse(body).decode("utf-8")
        self.assertNotIn("prompt_tokens", stripped)
        self.assertIn('"content":"ok"', stripped)
        self.assertIn("[DONE]", stripped)

    def test_ensure_stream_include_usage_only_on_streaming_requests(self) -> None:
        non_stream = {"model": "gpt-5.6-luna", "stream": False}
        body, payload, injected = _ensure_stream_include_usage(
            json.dumps(non_stream).encode("utf-8"),
            non_stream,
        )
        self.assertFalse(injected)
        self.assertEqual(payload, non_stream)

        streaming = {"model": "gpt-5.6-luna", "stream": True}
        _, payload, injected = _ensure_stream_include_usage(
            json.dumps(streaming).encode("utf-8"),
            streaming,
        )
        self.assertTrue(injected)
        self.assertEqual(payload["stream_options"]["include_usage"], True)

        _, _, responses_injected = _ensure_stream_include_usage(
            json.dumps(streaming).encode("utf-8"),
            streaming,
            path="/v1/responses",
        )
        self.assertFalse(responses_injected)

    def test_extract_usage_from_responses_completed_event(self) -> None:
        body = (
            "event: response.created\n"
            'data: {"type":"response.created","response":{"usage":null}}\n\n'
            "event: response.completed\n"
            'data: {"type":"response.completed","response":{"usage":{"input_tokens":13,"output_tokens":5,"total_tokens":18}}}\n\n'
        ).encode("utf-8")
        usage, source = _extract_provider_usage(body)
        self.assertEqual(source, "sse")
        self.assertEqual(usage["input_tokens"], 13)
        self.assertEqual(usage["output_tokens"], 5)
        self.assertEqual(usage["total_tokens"], 18)

    def test_proxy_records_sse_usage_after_injecting_include_usage(self) -> None:
        try:
            upstream = _FakeUpstreamServer()
        except PermissionError as exc:
            self.skipTest(f"local loopback sockets are unavailable: {exc}")
        upstream.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                proxy = LLMUsageProxy(
                    LLMUsageProxyConfig(
                        target_base_url=upstream.base_url + "/v1",
                        api_key="sk-real",
                        audit_path=root / "context_audit.jsonl",
                        usage_path=root / "openhands_usage.json",
                        model="gpt-5.6-luna",
                    )
                ).start()
                try:
                    body = json.dumps(
                        {
                            "model": "gpt-5.6-luna",
                            "messages": [{"role": "user", "content": "hello"}],
                            "stream": True,
                        }
                    ).encode("utf-8")
                    request = urllib.request.Request(
                        proxy.base_url + "/chat/completions",
                        data=body,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=10) as response:
                        forwarded = response.read().decode("utf-8")
                finally:
                    proxy.close()

                audit_records = [
                    json.loads(line)
                    for line in (root / "context_audit.jsonl").read_text(encoding="utf-8").splitlines()
                ]
                usage = json.loads((root / "openhands_usage.json").read_text(encoding="utf-8"))

            self.assertTrue(upstream.last_payload["stream_options"]["include_usage"])
            self.assertEqual(len(audit_records), 1)
            self.assertTrue(audit_records[0]["usage_verified"])
            self.assertTrue(audit_records[0]["stream_include_usage_injected"])
            self.assertEqual(audit_records[0]["usage_parse"], "sse")
            self.assertEqual(audit_records[0]["prompt_tokens"], 13)
            self.assertEqual(audit_records[0]["completion_tokens"], 4)
            self.assertEqual(usage["total_tokens"], 17)
            self.assertFalse(usage["context_audit"]["usage_unverified"])
            self.assertNotIn("prompt_tokens", forwarded)
            self.assertIn("[DONE]", forwarded)
        finally:
            upstream.close()

    def test_proxy_records_responses_api_sse_usage(self) -> None:
        try:
            upstream = _FakeUpstreamServer()
        except PermissionError as exc:
            self.skipTest(f"local loopback sockets are unavailable: {exc}")
        upstream.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                proxy = LLMUsageProxy(
                    LLMUsageProxyConfig(
                        target_base_url=upstream.base_url + "/v1",
                        api_key="sk-real",
                        audit_path=root / "context_audit.jsonl",
                        usage_path=root / "openhands_usage.json",
                        model="gpt-5.6-luna",
                    )
                ).start()
                try:
                    body = json.dumps(
                        {
                            "model": "gpt-5.6-luna",
                            "input": "hello",
                            "stream": True,
                        }
                    ).encode("utf-8")
                    request = urllib.request.Request(
                        proxy.base_url + "/responses",
                        data=body,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=10) as response:
                        forwarded = response.read().decode("utf-8")
                finally:
                    proxy.close()

                audit_records = [
                    json.loads(line)
                    for line in (root / "context_audit.jsonl").read_text(encoding="utf-8").splitlines()
                ]
                usage = json.loads((root / "openhands_usage.json").read_text(encoding="utf-8"))

            self.assertNotIn("stream_options", upstream.last_payload or {})
            self.assertEqual(len(audit_records), 1)
            self.assertTrue(audit_records[0]["usage_verified"])
            self.assertFalse(audit_records[0]["stream_include_usage_injected"])
            self.assertEqual(audit_records[0]["usage_parse"], "sse")
            self.assertEqual(audit_records[0]["prompt_tokens"], 13)
            self.assertEqual(audit_records[0]["completion_tokens"], 5)
            self.assertEqual(usage["total_tokens"], 18)
            self.assertIn("response.completed", forwarded)
        finally:
            upstream.close()

    def test_proxy_records_gzip_json_usage(self) -> None:
        try:
            upstream = _FakeUpstreamServer(gzip_json=True)
        except PermissionError as exc:
            self.skipTest(f"local loopback sockets are unavailable: {exc}")
        upstream.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                proxy = LLMUsageProxy(
                    LLMUsageProxyConfig(
                        target_base_url=upstream.base_url + "/v1",
                        api_key="sk-real",
                        audit_path=root / "context_audit.jsonl",
                        usage_path=root / "openhands_usage.json",
                        model="gpt-5.6-luna",
                    )
                ).start()
                try:
                    body = json.dumps(
                        {
                            "model": "gpt-5.6-luna",
                            "input": "hello",
                        }
                    ).encode("utf-8")
                    request = urllib.request.Request(
                        proxy.base_url + "/responses",
                        data=body,
                        headers={
                            "Content-Type": "application/json",
                            "Accept-Encoding": "gzip",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=10) as response:
                        response.read()
                finally:
                    proxy.close()

                audit_records = [
                    json.loads(line)
                    for line in (root / "context_audit.jsonl").read_text(encoding="utf-8").splitlines()
                ]
                usage = json.loads((root / "openhands_usage.json").read_text(encoding="utf-8"))

            self.assertTrue(audit_records[0]["usage_verified"])
            self.assertEqual(audit_records[0]["usage_parse"], "json")
            self.assertEqual(audit_records[0]["prompt_tokens"], 13)
            self.assertEqual(audit_records[0]["completion_tokens"], 5)
            self.assertEqual(usage["total_tokens"], 18)
        finally:
            upstream.close()


class _FakeUpstreamServer:
    def __init__(self, gzip_json: bool = False) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeUpstreamHandler)
        self.server.owner = self  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.last_path = ""
        self.last_authorization = ""
        self.last_payload: dict | None = None
        self.request_count = 0
        self.gzip_json = gzip_json

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class _FakeUpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        owner = self.server.owner  # type: ignore[attr-defined]
        owner.last_path = self.path
        owner.last_authorization = self.headers.get("Authorization", "")
        owner.request_count += 1
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        owner.last_payload = payload
        if str(self.path).rstrip("/").endswith("/responses") and not getattr(
            owner, "gzip_json", False
        ):
            completed = {
                "type": "response.completed",
                "response": {
                    "usage": {
                        "input_tokens": 13,
                        "output_tokens": 5,
                        "total_tokens": 18,
                    }
                },
            }
            sse = (
                "event: response.created\n"
                'data: {"type":"response.created","response":{"usage":null}}\n\n'
                "event: response.completed\n"
                "data: " + json.dumps(completed) + "\n\n"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(sse)))
            self.end_headers()
            self.wfile.write(sse)
            return
        if payload.get("stream") is True:
            chunks = [
                {"id": "chatcmpl-test", "choices": [{"index": 0, "delta": {"content": "ok"}}], "usage": None},
            ]
            options = payload.get("stream_options") if isinstance(payload.get("stream_options"), dict) else {}
            if options.get("include_usage") is True:
                chunks.append(
                    {
                        "id": "chatcmpl-test",
                        "choices": [],
                        "usage": {
                            "prompt_tokens": 13,
                            "completion_tokens": 4,
                            "total_tokens": 17,
                        },
                    }
                )
            body = "".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks)
            body += "data: [DONE]\n\n"
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        if getattr(owner, "gzip_json", False):
            body = gzip.compress(
                json.dumps(
                    {
                        "id": "resp-test",
                        "usage": {
                            "input_tokens": 13,
                            "output_tokens": 5,
                            "total_tokens": 18,
                        },
                    }
                ).encode("utf-8")
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = json.dumps(
            {
                "id": "chatcmpl-test",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {
                    "prompt_tokens": 123,
                    "completion_tokens": 45,
                    "total_tokens": 168,
                    "prompt_cache_hit_tokens": 100,
                    "prompt_cache_miss_tokens": 23,
                },
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    unittest.main()
