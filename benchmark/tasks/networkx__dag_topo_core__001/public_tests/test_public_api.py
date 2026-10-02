import pytest

from featurelifted import DiGraph
from featurelifted import is_directed_acyclic_graph
from featurelifted import topological_sort


def test_topological_sort_linear_dag() -> None:
    graph = DiGraph([("a", "b"), ("b", "c")])

    assert list(topological_sort(graph)) == ["a", "b", "c"]
    assert is_directed_acyclic_graph(graph) is True


def test_topological_sort_parallel_roots() -> None:
    graph = DiGraph([("a", "c"), ("b", "c")])

    order = list(topological_sort(graph))

    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("c")
