from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from featureliftbench.local_config import (
    apply_local_overrides,
    is_local_api_base,
    load_local_config,
    normalize_local_vllm_model,
    resolve_output_dir,
    resolve_runtime_policy,
    resolve_suite_preset,
)
from featureliftbench.llm_env import normalize_api_model_name


SAMPLE_CONFIG = """\
[llm]
model = "Qwen3-Coder-30B-A3B-Instruct"
base_url = "http://127.0.0.1:8008/v1"
api_key_env = "VLLM_QWEN3_CODER_30B_API_KEY"
native_tool_calling = true

[agent]
kind = "openhands-agent"
max_steps = 180

[run]
suite = "pilot5"
workers = 2
agent_docker = true
eval_docker = true
"""


class LocalConfigTests(unittest.TestCase):
    def test_load_local_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flb.local.toml"
            path.write_text(SAMPLE_CONFIG, encoding="utf-8")
            config = load_local_config(path)
            self.assertEqual(config.llm.model, "openai/Qwen3-Coder-30B-A3B-Instruct")
            self.assertEqual(config.run.suite, "pilot5")
            self.assertEqual(config.run.workers, 2)

    def test_resolve_suite_preset_pilot5(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flb.local.toml"
            path.write_text(SAMPLE_CONFIG, encoding="utf-8")
            preset = resolve_suite_preset(load_local_config(path))
            self.assertEqual(preset.name, "pilot5")
            self.assertTrue(preset.merge_pilot)
            self.assertEqual(len(preset.phases), 2)

    def test_resolve_suite_preset_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flb.local.toml"
            path.write_text(
                SAMPLE_CONFIG.replace('suite = "pilot5"', 'suite = "smoke"'),
                encoding="utf-8",
            )
            preset = resolve_suite_preset(load_local_config(path))
            self.assertEqual(preset.name, "smoke")
            self.assertTrue(preset.run_smoke_check)
            self.assertEqual(len(preset.phases), 1)
            self.assertIn("iniconfig__parse_config__001", str(preset.phases[0].task_root))

    def test_resolve_suite_preset_main_has_no_embedded_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flb.local.toml"
            path.write_text(
                SAMPLE_CONFIG.replace('suite = "pilot5"', 'suite = "main"'),
                encoding="utf-8",
            )
            preset = resolve_suite_preset(load_local_config(path))
            self.assertFalse(preset.run_smoke_check)
            self.assertTrue(preset.strict_preflight)
            self.assertEqual(len(preset.phases), 1)

    def test_resolve_output_dir_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flb.local.toml"
            path.write_text(
                SAMPLE_CONFIG.replace('suite = "pilot5"', 'suite = "smoke"'),
                encoding="utf-8",
            )
            config = load_local_config(path)
            preset = resolve_suite_preset(config)
            output = resolve_output_dir(config, suite_preset=preset)
            self.assertIn("smoke-", output.name)
            self.assertIn("/smoke/", output.as_posix())

    def test_runtime_policy_sets_host_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flb.local.toml"
            path.write_text(SAMPLE_CONFIG, encoding="utf-8")
            policy = resolve_runtime_policy(load_local_config(path))
            self.assertEqual(policy.env.get("FEATURELIFTBENCH_AGENT_DOCKER_NETWORK"), "host")
            self.assertEqual(policy.env.get("FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"), "180")

    def test_apply_local_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flb.local.toml"
            path.write_text(SAMPLE_CONFIG, encoding="utf-8")
            updated = apply_local_overrides(
                load_local_config(path),
                suite="sanity",
                max_steps=120,
                workers=1,
            )
            self.assertEqual(updated.run.suite, "sanity")
            self.assertEqual(updated.agent.max_steps, 120)
            self.assertEqual(updated.run.workers, 1)


class LlmEnvExtensionTests(unittest.TestCase):
    def test_normalize_local_vllm_model_adds_prefix(self) -> None:
        self.assertEqual(
            normalize_local_vllm_model("Qwen3-Coder-30B-A3B-Instruct", "http://127.0.0.1:8008/v1"),
            "openai/Qwen3-Coder-30B-A3B-Instruct",
        )

    def test_normalize_local_vllm_health_probe_strips_prefix(self) -> None:
        self.assertEqual(
            normalize_api_model_name(
                "openai/Qwen3-Coder-30B-A3B-Instruct",
                "http://127.0.0.1:8008/v1",
            ),
            "Qwen3-Coder-30B-A3B-Instruct",
        )

    def test_is_local_api_base(self) -> None:
        self.assertTrue(is_local_api_base("http://127.0.0.1:8008/v1"))
        self.assertFalse(is_local_api_base("https://api.deepseek.com/v1"))


if __name__ == "__main__":
    unittest.main()
