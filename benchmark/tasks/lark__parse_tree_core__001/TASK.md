# FeatureLift Task: LALR parse tree core

Extract a task-scoped subset of `lark` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Lark,
    Token,
    Tree,
    UnexpectedCharacters,
    UnexpectedToken,
)
```

## Required API Details

- `Lark(grammar: 'Union[Grammar, str, IO[str]]', **options) -> None` class constructor
  - `Lark.parse(self, text: str, start: Optional[str] = None, on_error: 'Optional[Callable[[UnexpectedInput], bool]]' = None) -> 'ParseTree'`
- `Tree(data: str, children: 'List[Branch[_Leaf_T]]', meta: Optional[Meta] = None) -> None` class constructor
- `Token(*args, **kwargs)` class constructor
- `UnexpectedToken` must be importable and raisable
- `UnexpectedCharacters` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: parse input with inline grammars using LALR. Required observable cases include parse builds tree with precedence; unexpected characters on garbage input.
- The extracted feature must support this observable behavior: build Tree nodes with rule data and Token leaves. Required observable cases include parse builds tree with precedence; nested lists and tokens.
- The extracted feature must support this observable behavior: support %import, %ignore, and common terminal imports. Required observable cases include named terminal and pretty output.
- The extracted feature must support this observable behavior: raise structured parse errors with line/column context. Required observable cases include parse error reports unexpected token; unexpected characters on garbage input.
- The extracted feature must support this observable behavior: expose pretty() and child navigation on trees. Required observable cases include named terminal and pretty output.
- The package exposes the required task API paths `featurelifted.Lark`, `featurelifted.Lark.parse`, `featurelifted.Tree`, `featurelifted.Token`, `featurelifted.UnexpectedToken`, `featurelifted.UnexpectedCharacters` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `lark`.
- Do not implement tree Transformer and Visitor APIs as public surface.
- Do not implement standalone code generation tools.
- Do not implement earley-only advanced forest transforms.
- Do not implement original project tests and documentation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse input with inline grammars using LALR. Required observable cases include parse builds tree with precedence; unexpected characters on garbage input.
- **B002** — The extracted feature must support this observable behavior: build Tree nodes with rule data and Token leaves. Required observable cases include parse builds tree with precedence; nested lists and tokens.
- **B003** — The extracted feature must support this observable behavior: support %import, %ignore, and common terminal imports. Required observable cases include named terminal and pretty output.
- **B004** — The extracted feature must support this observable behavior: raise structured parse errors with line/column context. Required observable cases include parse error reports unexpected token; unexpected characters on garbage input.
- **B005** — The extracted feature must support this observable behavior: expose pretty() and child navigation on trees. Required observable cases include named terminal and pretty output.
- **B006** — The package exposes the required task API paths `featurelifted.Lark`, `featurelifted.Lark.parse`, `featurelifted.Tree`, `featurelifted.Token`, `featurelifted.UnexpectedToken`, `featurelifted.UnexpectedCharacters` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: lark.
<!-- featureliftbench:behavior-clauses:end -->
