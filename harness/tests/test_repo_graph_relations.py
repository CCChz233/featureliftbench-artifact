"""Exact-edge fixtures for Phase 3 Operational Support relation families."""

from __future__ import annotations

import unittest
from pathlib import Path

from featureliftbench.repo_graph.builder import GraphBuilder
from featureliftbench.repo_graph.query import GraphQueryEngine


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "repo_graph_phase3"


class Phase3RelationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = GraphBuilder().build(FIXTURE)
        cls.engine = GraphQueryEngine(cls.snapshot)
        cls.edges = cls.snapshot.edges
        cls.nodes_by_id = {node.id: node for node in cls.snapshot.nodes}

    def _edges(self, kind: str) -> list:
        return [edge for edge in self.edges if edge.kind == kind]

    def _stable(self, node_id: int | None) -> str | None:
        if node_id is None:
            return None
        return self.nodes_by_id[node_id].stable_id

    def test_exports_from_all(self) -> None:
        exports = self._edges("EXPORTS")
        self.assertTrue(exports)
        targets = {
            edge.attributes.get("target_expression")
            if edge.target is None
            else self._stable(edge.target)
            for edge in exports
        }
        # Resolver may bind some exports to stable ids.
        names = {
            (
                self.nodes_by_id[edge.target].name
                if edge.target is not None
                else edge.attributes.get("target_expression")
            )
            for edge in exports
        }
        self.assertIn("PublicAPI", names)
        self.assertIn("dispatch", names)
        self.assertTrue(any(edge.source and True for edge in exports))
        del targets

    def test_provides_member_on_public_api(self) -> None:
        members = self._edges("PROVIDES_MEMBER")
        pairs = {
            (self._stable(edge.source), self.nodes_by_id[edge.target].name)
            for edge in members
            if edge.target is not None
        }
        self.assertIn(("python:pkg.api.PublicAPI:class", "run"), pairs)
        self.assertIn(("python:pkg.api.PublicAPI:class", "boom"), pairs)

    def test_returns_type_and_raises(self) -> None:
        returns = self._edges("RETURNS_TYPE")
        self.assertTrue(
            any(
                edge.attributes.get("target_expression") == "PublicAPI"
                or self._stable(edge.target) == "python:pkg.api.PublicAPI:class"
                for edge in returns
            )
        )
        raises = self._edges("RAISES")
        self.assertTrue(
            any(
                edge.attributes.get("target_expression", "").startswith("Error")
                or (edge.target is not None and self.nodes_by_id[edge.target].name == "Error")
                for edge in raises
            )
        )

    def test_reads_config_and_default_defined_by(self) -> None:
        configs = self._edges("READS_CONFIG")
        self.assertTrue(
            any(
                "config.json" in str(edge.attributes.get("target_expression", ""))
                or (
                    edge.target is not None
                    and "config.json" in self.nodes_by_id[edge.target].qualified_name
                )
                for edge in configs
            )
        )
        defaults = self._edges("DEFAULT_DEFINED_BY")
        self.assertTrue(
            any(
                edge.attributes.get("parameter") in {"mode", "value"}
                for edge in defaults
            )
        )

    def test_registers_and_resolves_via(self) -> None:
        registers = self._edges("REGISTERS")
        self.assertTrue(
            any(
                "register" in str(edge.attributes.get("target_expression", "")).casefold()
                for edge in registers
            )
        )
        resolves = self._edges("RESOLVES_VIA")
        self.assertTrue(
            any(
                "REGISTRY" in str(edge.attributes.get("target_expression", ""))
                or edge.attributes.get("dispatch_style") in {"subscript", "getattr"}
                for edge in resolves
            )
        )
        self.assertTrue(
            any(edge.resolution == "unresolved_dynamic" for edge in resolves)
        )

    def test_packaged_by_from_manifests(self) -> None:
        packaged = self._edges("PACKAGED_BY")
        self.assertTrue(packaged)
        self.assertTrue(
            any(
                edge.attributes.get("package") == "pkg"
                or "settings.toml" in str(edge.attributes.get("pattern", ""))
                or (
                    edge.source is not None
                    and "settings.toml" in self.nodes_by_id[edge.source].qualified_name
                )
                for edge in packaged
            )
        )

    def test_support_covers_new_categories(self) -> None:
        from featureliftbench.repo_graph.support import build_operational_support

        result = build_operational_support(
            self.engine,
            ["PublicAPI"],
            budget_tokens=4_000,
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["core"])
        kinds_seen = set()
        for item in result.get("support", []):
            kinds_seen.add(item.get("category"))
        # At least implementation/interface should appear for this fixture seed.
        self.assertTrue(kinds_seen & {"implementation", "interface", "dispatch", "configuration"})


if __name__ == "__main__":
    unittest.main()
