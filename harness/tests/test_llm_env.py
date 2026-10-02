from __future__ import annotations

import unittest

from featureliftbench.llm_env import apply_openhands_llm_env
from featureliftbench.llm_env import normalize_api_model_name


class LlmEnvTests(unittest.TestCase):
    def test_normalize_deepseek_model(self) -> None:
        self.assertEqual(
            normalize_api_model_name(
                "deepseek/deepseek-v4-flash",
                "https://api.deepseek.com/v1",
            ),
            "deepseek-v4-flash",
        )

    def test_normalize_local_vllm_model(self) -> None:
        self.assertEqual(
            normalize_api_model_name(
                "openai/Qwen3-Coder-30B-A3B-Instruct",
                "http://127.0.0.1:8008/v1",
            ),
            "Qwen3-Coder-30B-A3B-Instruct",
        )

    def test_normalize_openai_prefix_on_remote_compat_base(self) -> None:
        self.assertEqual(
            normalize_api_model_name(
                "openai/glm-5.3",
                "https://open.bigmodel.cn/api/paas/v4",
            ),
            "glm-5.3",
        )
        self.assertEqual(
            normalize_api_model_name(
                "openai/glm-5.3-flash",
                "https://open.bigmodel.cn/api/paas/v4",
            ),
            "glm-5.3-flash",
        )

    def test_apply_openhands_llm_env_maps_values(self) -> None:
        env = apply_openhands_llm_env(
            {
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_BASE_URL": "https://api.deepseek.com/v1",
                "FEATURELIFTBENCH_MODEL": "deepseek/deepseek-v4-flash",
            }
        )

        self.assertEqual(env["LLM_API_KEY"], "sk-test")
        self.assertEqual(env["LLM_BASE_URL"], "https://api.deepseek.com/v1")
        self.assertEqual(env["LLM_MODEL"], "deepseek/deepseek-v4-flash")


if __name__ == "__main__":
    unittest.main()
