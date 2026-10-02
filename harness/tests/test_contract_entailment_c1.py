"""C1 surface visitor: scoped bindings, no class-body leak into functions."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "harness" / "scripts"))

from audit_contract_entailment import (  # noqa: E402
    Contract,
    exercised_members,
    members_used_in_source,
)

GRAPHENE = (
    _REPO
    / "benchmark"
    / "python200_hard_tasks"
    / "graphene__schema_execute_core__001"
)

CIMULTIDICT_SPEC = {
    "required_api": [
        {
            "path": "featurelifted.CIMultiDict",
            "kind": "class",
            "members": [
                {
                    "path": "featurelifted.CIMultiDict.getall",
                    "kind": "method",
                }
            ],
        }
    ]
}


def _undeclared(used: set[str], contract: Contract) -> set[str]:
    return {
        member
        for member in used
        if member.split(".")[0] in contract.tops and member not in contract.members
    }


class C1ScopeTests(unittest.TestCase):
    def test_function_subscript_still_records_declared_class(self) -> None:
        source = """
from featurelifted import CIMultiDict

def test_headers() -> None:
    headers = CIMultiDict()
    headers["X"] = "1"
    assert "x" in headers
    del headers["X"]
"""
        contract = Contract(CIMULTIDICT_SPEC)
        used = members_used_in_source(source, contract)
        self.assertIn("CIMultiDict.__setitem__", used)
        self.assertIn("CIMultiDict.__contains__", used)
        self.assertIn("CIMultiDict.__delitem__", used)

    def test_unknown_reassignment_clears_old_binding(self) -> None:
        source = """
from featurelifted import CIMultiDict

def test_rebind() -> None:
    headers = CIMultiDict()
    headers["keep"] = "1"
    headers = load()
    headers["drop"] = "2"
"""
        contract = Contract(CIMULTIDICT_SPEC)
        used = members_used_in_source(source, contract)
        self.assertEqual(used, {"CIMultiDict.__setitem__"})

    def test_class_field_name_does_not_leak_into_function(self) -> None:
        source = """
from featurelifted import Schema, String

class Query:
    hello = String()

def test_execute() -> None:
    hello = Schema().execute("{ hello }")
    assert hello.errors is None
    assert hello.data == {"hello": "ok"}
"""
        contract = Contract(
            {
                "required_api": [
                    {"path": "featurelifted.String", "kind": "class"},
                    {
                        "path": "featurelifted.Schema",
                        "kind": "class",
                        "members": [
                            {
                                "path": "featurelifted.Schema.execute",
                                "kind": "method",
                            }
                        ],
                    },
                ]
            }
        )
        used = members_used_in_source(source, contract)
        undeclared = _undeclared(used, contract)
        self.assertNotIn("String.data", used)
        self.assertNotIn("String.errors", used)
        self.assertNotIn("String.data", undeclared)
        self.assertNotIn("String.errors", undeclared)

    def test_graphene_hidden_tests_do_not_attribute_result_fields_to_string(self) -> None:
        if not GRAPHENE.is_dir():
            self.skipTest(f"missing {GRAPHENE}")
        metadata = json.loads((GRAPHENE / "metadata.json").read_text(encoding="utf-8"))
        contract = Contract(metadata.get("public_spec") or {})
        used = exercised_members(GRAPHENE / "hidden_tests", contract)
        undeclared = _undeclared(used, contract)
        self.assertNotIn("String.data", used)
        self.assertNotIn("String.errors", used)
        self.assertNotIn("String.data", undeclared)
        self.assertNotIn("String.errors", undeclared)


if __name__ == "__main__":
    unittest.main()
