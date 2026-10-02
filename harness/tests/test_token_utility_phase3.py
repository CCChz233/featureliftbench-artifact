from __future__ import annotations

import json
import unittest

from featureliftbench.token_utility_signals import (
    COMPUTED_FEATURE_KEYS,
    LEGAL_FEATURE_KEYS,
    annotate_novelty,
    assert_legal_features,
    attach_action_features,
    classify_self_test_event,
    command_hash,
    features_from_history,
    label_already_enough,
    label_still_necessary,
    observation_hash,
    pair_hash,
    roc_auc,
)


def _action(**kwargs):
    row = {
        "ts": kwargs.get("ts", 0.0),
        "tokens": kwargs.get("tokens", 0),
        "cat": kwargs.get("cat", "other"),
        "tool": kwargs.get("tool", "terminal"),
        "command": kwargs.get("command", ""),
        "path": kwargs.get("path", ""),
        "path_key": kwargs.get("path_key", ""),
        "summary": "",
        "cmd_hash": kwargs.get("cmd_hash", command_hash(kwargs.get("command", ""))),
        "out_hash": kwargs.get("out_hash", observation_hash(kwargs.get("obs", ""), kwargs.get("exit_code"))),
        "pair_hash": "",
        "exit_code": kwargs.get("exit_code"),
    }
    row["pair_hash"] = pair_hash(row["cmd_hash"], row["out_hash"]) if row["cmd_hash"] or row["out_hash"] else ""
    return row


class NoveltyHashTests(unittest.TestCase):
    def test_heredoc_body_does_not_change_command_hash(self) -> None:
        a = command_hash("cat > /tmp/t.py << 'EOF'\nprint(1)\nEOF\npython3 /tmp/t.py")
        b = command_hash("cat > /tmp/t.py << 'EOF'\nprint(2)\nEOF\npython3 /tmp/t.py")
        self.assertEqual(a, b)

    def test_command_hash_ignores_whitespace(self) -> None:
        self.assertEqual(command_hash("pytest   -q"), command_hash("pytest -q"))
        self.assertNotEqual(command_hash("pytest -q"), command_hash("pytest -vv"))

    def test_bracketed_paste_ansi_does_not_change_pytest_hash(self) -> None:
        a = observation_hash("\x1b[?2004l25 passed in 0.09s\x1b[?2004h", 0)
        b = observation_hash("25 passed in 1.80s", 0)
        self.assertEqual(a, b)

    def test_observation_hash_strips_pytest_timing(self) -> None:
        a = observation_hash("===== 3 passed in 0.12s =====", 0)
        b = observation_hash("===== 3 passed in 1.80s =====", 0)
        c = observation_hash("===== 2 passed in 0.12s =====", 0)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_identical_rerun_vs_new_output(self) -> None:
        actions = [
            _action(cat="self_test_run", command="pytest -q", obs="3 passed", tokens=10),
            _action(cat="self_test_run", command="pytest -q", obs="3 passed", tokens=20),
            _action(cat="self_test_run", command="pytest -q", obs="2 failed", tokens=30),
        ]
        annotate_novelty(actions)
        self.assertTrue(actions[0]["pair_novel"])
        self.assertTrue(actions[1]["identical_rerun"])
        self.assertFalse(actions[1]["out_novel"])
        self.assertTrue(actions[2]["out_novel"])
        self.assertFalse(actions[2]["cmd_novel"])
        self.assertTrue(actions[2]["pair_novel"])


class LabelTests(unittest.TestCase):
    def test_t_lt_tstar_is_still_necessary(self) -> None:
        self.assertEqual(label_still_necessary(99, 100), 1)
        self.assertEqual(label_already_enough(99, 100), 0)
        self.assertEqual(label_still_necessary(100, 100), 0)
        self.assertEqual(label_already_enough(100, 100), 1)
        self.assertIsNone(label_already_enough(None, 100))


class FeatureLeakageTests(unittest.TestCase):
    def test_assert_legal_features_rejects_tstar(self) -> None:
        with self.assertRaises(ValueError):
            assert_legal_features({"consecutive_self_tests": 1.0, "t_star": 9})

    def test_feature_keys_do_not_contain_tstar(self) -> None:
        unique = [
            {"tree_hash": "a", "tokens": 50, "n_bytes": 10},
            {"tree_hash": "b", "tokens": 500, "n_bytes": 20},
        ]
        actions = [
            _action(cat="package_write", command="edit pkg", tokens=50, path="submission/featurelifted/x.py"),
            _action(cat="self_test_run", command="pytest -q", obs="fail", tokens=80),
            _action(cat="self_test_run", command="pytest -q", obs="fail", tokens=90),
        ]
        annotate_novelty(actions)
        feats = features_from_history(actions, 2, unique=unique)
        assert_legal_features(feats)
        blob = json.dumps(feats).lower()
        for needle in ("tstar", "t_star", "earliest", "hidden", "functional_gate"):
            self.assertNotIn(needle, blob)
        self.assertEqual(set(feats), set(COMPUTED_FEATURE_KEYS))
        self.assertTrue(set(LEGAL_FEATURE_KEYS).issubset(feats))
        self.assertEqual(feats["unique_trees_so_far"], 1.0)
        self.assertEqual(feats["consecutive_self_tests"], 2.0)

    def test_future_trees_are_not_in_features(self) -> None:
        unique = [
            {"tree_hash": "a", "tokens": 10, "n_bytes": 1},
            {"tree_hash": "future", "tokens": 999, "n_bytes": 99},
        ]
        actions = [_action(cat="package_write", command="edit", tokens=10)]
        annotate_novelty(actions)
        feats = features_from_history(actions, 0, unique=unique)
        self.assertEqual(feats["unique_trees_so_far"], 1.0)
        self.assertEqual(feats["last_tree_n_bytes"], 1.0)


class UsefulVerificationTests(unittest.TestCase):
    def test_pre_tstar_novel_test_then_patch_is_useful(self) -> None:
        unique = [
            {"tree_hash": "a", "tokens": 10},
            {"tree_hash": "b", "tokens": 40},
        ]
        actions = [
            _action(cat="self_test_run", command="pytest -q", obs="fail", tokens=20),
            _action(cat="package_write", command="str_replace", tokens=30, path="submission/featurelifted/x.py"),
            _action(cat="self_test_run", command="pytest -q", obs="pass", tokens=50),
        ]
        annotate_novelty(actions)
        pre = classify_self_test_event(actions[0], t_star=40, unique=unique, actions=actions, index=0)
        post = classify_self_test_event(actions[2], t_star=40, unique=unique, actions=actions, index=2)
        self.assertTrue(pre["before_tstar"])
        self.assertTrue(pre["useful_strict"])
        self.assertTrue(pre["useful_loose"])
        self.assertFalse(post["before_tstar"])
        self.assertFalse(post["useful_strict"])
        self.assertFalse(post["useful_loose"])

    def test_far_later_tree_is_not_useful_loose(self) -> None:
        unique = [
            {"tree_hash": "a", "tokens": 10},
            {"tree_hash": "b", "tokens": 800_000},
        ]
        actions = [
            _action(cat="self_test_run", command="pytest -q", obs="1 failed", tokens=20),
            _action(cat="self_test_run", command="pytest -q", obs="1 passed", tokens=30),
        ]
        annotate_novelty(actions)
        row = classify_self_test_event(
            actions[0], t_star=800_000, unique=unique, actions=actions, index=0
        )
        self.assertTrue(row["before_tstar"])
        self.assertFalse(row["useful_loose"])
        self.assertFalse(row["followed_by_new_tree_soon"])

    def test_attach_features_then_label_separately(self) -> None:
        actions = [
            _action(cat="self_test_run", command="pytest", obs="a", tokens=10),
            _action(cat="self_test_run", command="pytest", obs="a", tokens=80),
        ]
        attach_action_features(actions, unique=[{"tree_hash": "a", "tokens": 5, "n_bytes": 1}])
        self.assertNotIn("t_star", actions[0]["features"])
        self.assertEqual(label_already_enough(actions[0]["tokens"], 50), 0)
        self.assertEqual(label_already_enough(actions[1]["tokens"], 50), 1)


class AucTests(unittest.TestCase):
    def test_separated_scores_auc_one(self) -> None:
        y = [0, 0, 1, 1]
        s = [0.1, 0.2, 0.8, 0.9]
        self.assertAlmostEqual(roc_auc(y, s) or 0, 1.0)
        self.assertAlmostEqual(roc_auc(y, [1 - v for v in s]) or 0, 0.0)

    def test_chance_and_ties(self) -> None:
        y = [0, 1, 0, 1]
        self.assertAlmostEqual(roc_auc(y, [0.5, 0.5, 0.5, 0.5]) or 0, 0.5)
        self.assertIsNone(roc_auc([1, 1, 1], [0.1, 0.2, 0.3]))


if __name__ == "__main__":
    unittest.main()
