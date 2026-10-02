from __future__ import annotations

import unittest

from featureliftbench.trajectory_audit import audit_trajectory


class TrajectoryAuditTests(unittest.TestCase):
    def test_repeated_reads_probes_and_fresh_verification(self) -> None:
        events = [
            {"action": {"kind": "FileEditorAction", "command": "view", "path": "/flb/workspace/repo/pkg/core.py"}},
            {"action": {"kind": "FileEditorAction", "command": "view", "path": "/flb/workspace/repo/pkg/core.py"}},
            {"action": {"kind": "TerminalAction", "command": "python -c 'print(1)'"}},
            {"action": {"kind": "FileEditorAction", "command": "create", "path": "/flb/workspace/submission/featurelifted/core.py"}},
            {"action": {"kind": "TerminalAction", "command": "pytest public_tests/"}, "system_fingerprint": "fp-1"},
            {"action": {"kind": "TerminalAction", "command": "pytest public_tests/"}},
        ]
        result = audit_trajectory(events)
        self.assertEqual(result["unchanged_repeated_reads"], 1)
        self.assertEqual(result["runtime_probe_count"], 1)
        self.assertEqual(result["exact_repeated_terminal_commands"], 1)
        self.assertTrue(result["fresh_final_verification"])
        self.assertTrue(result["fresh_public_verification"])
        self.assertEqual(result["system_fingerprints"], ["fp-1"])


if __name__ == "__main__":
    unittest.main()
