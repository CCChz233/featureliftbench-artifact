import pytest

from featurelifted import DiGraph
from featurelifted import Graph
from featurelifted import lexicographical_topological_sort
from featurelifted import topological_generations
from featurelifted import topological_sort
from featurelifted.exception import NetworkXError
from featurelifted.exception import NetworkXUnfeasible


def test_lexicographical_topological_sort_is_stable() -> None:
    graph = DiGraph([("c", "a"), ("a", "b"), ("b", "d")])

    assert list(lexicographical_topological_sort(graph)) == ["c", "a", "b", "d"]


def test_topological_generations_layers() -> None:
    graph = DiGraph([("c", "a"), ("a", "b"), ("b", "d")])

    generations = [list(layer) for layer in topological_generations(graph)]

    assert generations == [["c"], ["a"], ["b"], ["d"]]


def test_cycle_raises_networkx_unfeasible() -> None:
    graph = DiGraph([("a", "b"), ("b", "a")])

    with pytest.raises(NetworkXUnfeasible):
        list(topological_sort(graph))


def test_undirected_graph_raises_networkx_error() -> None:
    graph = Graph([("a", "b")])

    with pytest.raises(NetworkXError):
        list(topological_sort(graph))
