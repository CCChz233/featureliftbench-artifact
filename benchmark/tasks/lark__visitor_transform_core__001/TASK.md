# FeatureLift Task: Parse tree visitor and transformer

Extract a task-scoped subset of `lark` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Discard,
    Lark,
    Transformer,
    Tree,
    v_args,
    Visitor,
)
```

## Required API Details

- `Lark(grammar: 'Union[Grammar, str, IO[str]]', **options) -> None` class constructor
  - `Lark.parse(self, text: str, start: Optional[str] = None, on_error: 'Optional[Callable[[UnexpectedInput], bool]]' = None) -> 'ParseTree'`
- `Tree(data: str, children: 'List[Branch[_Leaf_T]]', meta: Optional[Meta] = None) -> None` class constructor
- `Transformer(visit_tokens: bool = True) -> None` class constructor
  - `Transformer.transform(self, tree: Tree[~_Leaf_T]) -> ~_Return_T`
- `Visitor()` class constructor
- `v_args(inline: bool = False, meta: bool = False, tree: bool = False, wrapper: Optional[Callable] = None) -> Callable[[Union[Callable[..., ~_Return_T], type]], Union[Callable[..., ~_Return_T], type]]`
- `Discard` object must exist

## Required Behavior

- The extracted feature must support this observable behavior: walk trees with Visitor callbacks. Required observable cases include visitor walks tree nodes.
- The extracted feature must support this observable behavior: transform trees bottom-up with Transformer. Required observable cases include transformer evaluates expression; v args inline transform; visitor walks tree nodes.
- The extracted feature must support this observable behavior: decorate transformer methods with v_args inline and tree modes. Required observable cases include transformer evaluates expression; v args inline transform; v args tree mode.
- The extracted feature must support this observable behavior: discard nodes using Discard sentinel. Required observable cases include discard removes nodes.
- The extracted feature must support this observable behavior: parse grammars needed to produce trees for transformation. Required observable cases include visitor walks tree nodes.
- The package exposes the required task API paths `featurelifted.Lark`, `featurelifted.Lark.parse`, `featurelifted.Tree`, `featurelifted.Transformer`, `featurelifted.Transformer.transform`, `featurelifted.Visitor`, `featurelifted.v_args`, `featurelifted.Discard` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `lark`.
- Do not implement standalone compiler tools and CLI.
- Do not implement tree reconstruction and template utilities.
- Do not implement original project tests and documentation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: walk trees with Visitor callbacks. Required observable cases include visitor walks tree nodes.
- **B002** — The extracted feature must support this observable behavior: transform trees bottom-up with Transformer. Required observable cases include transformer evaluates expression; v args inline transform; visitor walks tree nodes.
- **B003** — The extracted feature must support this observable behavior: decorate transformer methods with v_args inline and tree modes. Required observable cases include transformer evaluates expression; v args inline transform; v args tree mode.
- **B004** — The extracted feature must support this observable behavior: discard nodes using Discard sentinel. Required observable cases include discard removes nodes.
- **B005** — The extracted feature must support this observable behavior: parse grammars needed to produce trees for transformation. Required observable cases include visitor walks tree nodes.
- **B006** — The package exposes the required task API paths `featurelifted.Lark`, `featurelifted.Lark.parse`, `featurelifted.Tree`, `featurelifted.Transformer`, `featurelifted.Transformer.transform`, `featurelifted.Visitor`, `featurelifted.v_args`, `featurelifted.Discard` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: lark.
<!-- featureliftbench:behavior-clauses:end -->
