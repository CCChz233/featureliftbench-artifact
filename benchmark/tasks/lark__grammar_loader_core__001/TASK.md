# FeatureLift Task: Grammar file loading

Extract a task-scoped subset of `lark` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    exceptions,
    Lark,
    load_grammar,
)
```

## Required API Details

- `Lark(grammar: 'Union[Grammar, str, IO[str]]', **options) -> None` class constructor
  - `Lark.open(grammar_filename: str, rel_to: Optional[str] = None, **options) -> ~_T`
  - `Lark.parse(self, text: Union[~AnyStr, TextSlice[~AnyStr], Any], start: Optional[str] = None, on_error: 'Optional[Callable[[UnexpectedInput], bool]]' = None) -> 'ParseTree'`
- `exceptions` module must be importable
  - `exceptions.GrammarError` must be importable and raisable
- `load_grammar` module must be importable
  - `load_grammar.FromPackageLoader(pkg_name: str, search_paths: Sequence[str] = ('',)) -> None` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: load grammars from strings and files with Lark.open(rel_to=...). Required observable cases include open relative import and common import; open from package and import graph.
- The extracted feature must support this observable behavior: resolve relative %import directives across grammar files. Required observable cases include open relative import and common import; packaged common grammar import.
- The extracted feature must support this observable behavior: load packaged grammars via open_from_package and %import common.*. Required observable cases include open relative import and common import; open from package and import graph; packaged common grammar import.
- The extracted feature must support this observable behavior: parse inputs with lalr after grammar compilation. Required observable cases include packaged common grammar import.
- The package exposes the required task API paths `featurelifted.Lark`, `featurelifted.Lark.open`, `featurelifted.Lark.parse`, `featurelifted.exceptions`, `featurelifted.exceptions.GrammarError`, `featurelifted.load_grammar`, `featurelifted.load_grammar.FromPackageLoader` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `lark`.
- Do not implement standalone codegen tools and CLI.
- Do not implement serialization caches beyond compile-time loading.
- Do not implement original project tests.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: load grammars from strings and files with Lark.open(rel_to=...). Required observable cases include open relative import and common import; open from package and import graph.
- **B002** — The extracted feature must support this observable behavior: resolve relative %import directives across grammar files. Required observable cases include open relative import and common import; packaged common grammar import.
- **B003** — The extracted feature must support this observable behavior: load packaged grammars via open_from_package and %import common.*. Required observable cases include open relative import and common import; open from package and import graph; packaged common grammar import.
- **B004** — The extracted feature must support this observable behavior: parse inputs with lalr after grammar compilation. Required observable cases include packaged common grammar import.
- **B005** — The package exposes the required task API paths `featurelifted.Lark`, `featurelifted.Lark.open`, `featurelifted.Lark.parse`, `featurelifted.exceptions`, `featurelifted.exceptions.GrammarError`, `featurelifted.load_grammar`, `featurelifted.load_grammar.FromPackageLoader` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: lark.
<!-- featureliftbench:behavior-clauses:end -->
