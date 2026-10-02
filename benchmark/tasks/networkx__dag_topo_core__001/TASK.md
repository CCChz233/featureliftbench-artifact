# FeatureLift Task: DAG topological sorting

Extract a task-scoped subset of `networkx` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    DiGraph,
    exception,
    Graph,
    is_directed_acyclic_graph,
    lexicographical_topological_sort,
    topological_generations,
    topological_sort,
)
```

## Required API Details

- `DiGraph(incoming_graph_data=None, **attr)` class constructor
- `Graph(incoming_graph_data=None, **attr)` class constructor
- `topological_sort(G, *, backend=None, **backend_kwargs)`
- `topological_generations(G, *, backend=None, **backend_kwargs)`
- `lexicographical_topological_sort(G, key=None, *, backend=None, **backend_kwargs)`
- `is_directed_acyclic_graph(G, *, backend=None, **backend_kwargs)`
- `exception` module must be importable
  - `exception.NetworkXError` must be importable and raisable
  - `exception.NetworkXUnfeasible` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: construct directed graphs and add edges. Required observable cases include undirected graph raises networkx error.
- The extracted feature must support this observable behavior: yield nodes in topological sort order for DAGs. Required observable cases include topological sort linear dag; topological sort parallel roots; lexicographical topological sort is stable.
- The extracted feature must support this observable behavior: yield lexicographically stable topological orderings. Required observable cases include lexicographical topological sort is stable.
- The extracted feature must support this observable behavior: yield topological generations (Kahn layers). Required observable cases include topological generations layers.
- The extracted feature must support this observable behavior: detect directed acyclic graphs. Required observable cases include undirected graph raises networkx error.
- The extracted feature must support this observable behavior: raise NetworkXError for undirected graphs and NetworkXUnfeasible for cycles. Required observable cases include cycle raises networkx unfeasible; undirected graph raises networkx error.
- The package exposes the required task API paths `featurelifted.DiGraph`, `featurelifted.Graph`, `featurelifted.topological_sort`, `featurelifted.topological_generations`, `featurelifted.lexicographical_topological_sort`, `featurelifted.is_directed_acyclic_graph`, `featurelifted.exception`, `featurelifted.exception.NetworkXError`, `featurelifted.exception.NetworkXUnfeasible` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `networkx`.
- Do not implement full NetworkX algorithm suite and drawing backends.
- Do not implement SciPy/NumPy graph backends.
- Do not implement original project tests and documentation.
- Do not implement graph I/O formats and generators beyond empty_graph helper.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: construct directed graphs and add edges. Required observable cases include undirected graph raises networkx error.
- **B002** — The extracted feature must support this observable behavior: yield nodes in topological sort order for DAGs. Required observable cases include topological sort linear dag; topological sort parallel roots; lexicographical topological sort is stable.
- **B003** — The extracted feature must support this observable behavior: yield lexicographically stable topological orderings. Required observable cases include lexicographical topological sort is stable.
- **B004** — The extracted feature must support this observable behavior: yield topological generations (Kahn layers). Required observable cases include topological generations layers.
- **B005** — The extracted feature must support this observable behavior: detect directed acyclic graphs. Required observable cases include undirected graph raises networkx error.
- **B006** — The extracted feature must support this observable behavior: raise NetworkXError for undirected graphs and NetworkXUnfeasible for cycles. Required observable cases include cycle raises networkx unfeasible; undirected graph raises networkx error.
- **B007** — The package exposes the required task API paths `featurelifted.DiGraph`, `featurelifted.Graph`, `featurelifted.topological_sort`, `featurelifted.topological_generations`, `featurelifted.lexicographical_topological_sort`, `featurelifted.is_directed_acyclic_graph`, `featurelifted.exception`, `featurelifted.exception.NetworkXError`, `featurelifted.exception.NetworkXUnfeasible` with the kinds and callable signatures listed in this contract.
- **B008** — the submitted package does not import forbidden upstream packages: networkx.
<!-- featureliftbench:behavior-clauses:end -->
