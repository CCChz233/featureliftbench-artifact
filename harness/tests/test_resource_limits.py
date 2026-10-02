"""Tests for POSIX memory limits and subprocess helpers."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.resource_limits import CapturedCommandResult
from featureliftbench.resource_limits import apply_agent_memory_limit
from featureliftbench.resource_limits import command_result_resource_fields
from featureliftbench.resource_limits import detect_resource_limited
from featureliftbench.resource_limits import memory_limit_supported
from featureliftbench.resource_limits import parse_memory_limit_mb
from featureliftbench.resource_limits import run_captured_command
from featureliftbench.resource_limits import wrap_command_with_memory_limit


class ParseMemoryLimitTests(unittest.TestCase):
    def test_parse_disabled_values(self) -> None:
        self.assertIsNone(parse_memory_limit_mb(None))
        self.assertIsNone(parse_memory_limit_mb(""))
        self.assertIsNone(parse_memory_limit_mb("0"))
        self.assertIsNone(parse_memory_limit_mb("-1"))

    def test_parse_positive_value(self) -> None:
        self.assertEqual(parse_memory_limit_mb("4096"), 4096)


class WrapCommandTests(unittest.TestCase):
    def test_wrap_adds_run_limited_module(self) -> None:
        if not memory_limit_supported():
            self.skipTest("memory limits are not supported on this platform")
        wrapped = wrap_command_with_memory_limit(["pytest", "tests/"], 512)
        self.assertEqual(wrapped[0], sys.executable)
        self.assertEqual(wrapped[3], "featureliftbench.run_limited")
        self.assertEqual(wrapped[4], "512")
        self.assertEqual(wrapped[5:], ["pytest", "tests/"])

    def test_wrap_skips_when_unlimited(self) -> None:
        command = ["pytest", "tests/"]
        self.assertEqual(wrap_command_with_memory_limit(command, None), command)

    def test_apply_agent_memory_limit_reads_env(self) -> None:
        if not memory_limit_supported():
            self.skipTest("memory limits are not supported on this platform")
        env = {"AGENT_MEMORY_MB": "1024"}
        wrapped = apply_agent_memory_limit(["mini"], env)
        self.assertIn("1024", wrapped)


class DetectResourceLimitedTests(unittest.TestCase):
    def test_detects_sigkill_exit_codes(self) -> None:
        self.assertTrue(detect_resource_limited(returncode=137, stderr=""))
        self.assertTrue(detect_resource_limited(returncode=-9, stderr=""))

    def test_detects_stderr_markers(self) -> None:
        self.assertTrue(
            detect_resource_limited(returncode=1, stderr="Cannot allocate memory")
        )


class RunCapturedCommandTests(unittest.TestCase):
    def test_successful_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_captured_command(
                [sys.executable, "-c", "print('ok')"],
                cwd=Path(tmp),
                env=os.environ.copy(),
                timeout_seconds=30,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("ok", result.stdout)
            self.assertFalse(result.resource_limited)

    def test_timeout_kills_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_captured_command(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                cwd=Path(tmp),
                env=os.environ.copy(),
                timeout_seconds=1,
            )
            self.assertTrue(result.timed_out)
            self.assertEqual(result.returncode, 124)

    def test_memory_limit_rejects_large_allocation(self) -> None:
        if not memory_limit_supported():
            self.skipTest("memory limits are not supported on this platform")
        with tempfile.TemporaryDirectory() as tmp:
            script = (
                "data = bytearray(256 * 1024 * 1024)\n"
                "print(len(data))\n"
            )
            result = run_captured_command(
                [sys.executable, "-c", script],
                cwd=Path(tmp),
                env=os.environ.copy(),
                timeout_seconds=30,
                memory_mb=64,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.resource_limited or result.returncode in (137, -9, 1))

    def test_output_limit_truncates_and_stops_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = (
                "import sys, time\n"
                "sys.stdout.write('x' * 10000)\n"
                "sys.stdout.flush()\n"
                "time.sleep(60)\n"
            )
            result = run_captured_command(
                [sys.executable, "-c", script],
                cwd=Path(tmp),
                env=os.environ.copy(),
                timeout_seconds=30,
                output_limit_bytes=1024,
            )

            self.assertTrue(result.log_limit_exceeded)
            self.assertTrue(result.stdout_truncated)
            self.assertLessEqual(len(result.stdout.encode("utf-8")), 1024)


class CommandResultResourceFieldsTests(unittest.TestCase):
    def test_resource_limited_reason(self) -> None:
        fields = command_result_resource_fields(
            CapturedCommandResult(
                returncode=137,
                duration_seconds=1.0,
                stdout="",
                stderr="killed",
                resource_limited=True,
            )
        )
        self.assertTrue(fields["resource_limited"])
        self.assertEqual(fields["reason"], "memory limit exceeded")

    def test_log_limit_reason(self) -> None:
        fields = command_result_resource_fields(
            CapturedCommandResult(
                returncode=-9,
                duration_seconds=1.0,
                stdout="x",
                stderr="",
                stdout_truncated=True,
                log_limit_exceeded=True,
            )
        )
        self.assertTrue(fields["log_limit_exceeded"])
        self.assertTrue(fields["stdout_truncated"])
        self.assertEqual(fields["reason"], "command output exceeded log limit")


class RunLimitedModuleTests(unittest.TestCase):
    def test_run_limited_executes_child(self) -> None:
        if not memory_limit_supported():
            self.skipTest("memory limits are not supported on this platform")
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "featureliftbench.run_limited",
                "512",
                sys.executable,
                "-c",
                "print('limited')",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("limited", completed.stdout)


if __name__ == "__main__":
    unittest.main()
