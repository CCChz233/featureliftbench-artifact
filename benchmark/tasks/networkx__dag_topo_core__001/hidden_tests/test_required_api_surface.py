"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    DiGraph,
    Graph,
    topological_sort,
    topological_generations,
    lexicographical_topological_sort,
    is_directed_acyclic_graph,
    exception,
)


def test_required_api_surface():
    assert isinstance(DiGraph, type)
    assert isinstance(Graph, type)
    assert callable(topological_sort)
    assert callable(topological_generations)
    assert callable(lexicographical_topological_sort)
    assert callable(is_directed_acyclic_graph)
    assert exception is not None
    assert issubclass(getattr(exception, 'NetworkXError'), BaseException)
    assert issubclass(getattr(exception, 'NetworkXUnfeasible'), BaseException)
