# FeatureLift Task: Regex lexer core

Extract a task-scoped subset of `pygments` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    get_lexer_by_name,
    lex,
    PythonLexer,
    token,
)
```

## Required API Details

- `lex(code, lexer)`
- `get_lexer_by_name(_alias, **options)`
- `PythonLexer(*args, **kwds)` class constructor
- `token` module must be importable
  - `token.Comment` attribute must exist
  - `token.Keyword` attribute must exist
  - `token.Literal` attribute must exist
  - `token.Name` attribute must exist
  - `token.Number` attribute must exist
  - `token.Operator` attribute must exist
  - `token.String` attribute must exist
  - `token.Text` attribute must exist
- `token.Comment.Single` attribute must exist
- `token.Literal.String` attribute must exist
- `token.Name.Function` attribute must exist
- `token.Number.Integer` attribute must exist
- `token.String.Double` attribute must exist
- `token.Literal.String.Single` attribute must exist

## Required Behavior

- The extracted feature must support this observable behavior: tokenize Python source with PythonLexer and lex(). Required observable cases include python lexer keywords and names; get lexer by name returns python lexer; triple quoted string and operator tokens.
- The extracted feature must support this observable behavior: resolve lexers by alias with get_lexer_by_name. Required observable cases include get lexer by name returns python lexer; triple quoted string and operator tokens.
- The extracted feature must support this observable behavior: emit Token types for keywords, strings, comments, numbers, operators, and names. Required observable cases include string and comment tokens are distinct; triple quoted string and operator tokens.
- The extracted feature must support this observable behavior: honor lexer options such as stripall and ensurenl. Required observable cases include stripall option removes whitespace tokens.
- The extracted feature must support this observable behavior: support modeline and encoding helpers used by lexer lookup. Required observable cases include triple quoted string and operator tokens.
- The package exposes the required task API paths `featurelifted.lex`, `featurelifted.get_lexer_by_name`, `featurelifted.PythonLexer`, `featurelifted.token`, `featurelifted.token.Comment`, `featurelifted.token.Keyword`, `featurelifted.token.Literal`, `featurelifted.token.Name`, `featurelifted.token.Number`, `featurelifted.token.Operator`, `featurelifted.token.String`, `featurelifted.token.Text`, and 6 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pygments`.
- Do not implement HTML, LaTeX, terminal, and other formatters.
- Do not implement command-line pygmentize tool.
- Do not implement hundreds of non-Python language lexers.
- Do not implement original project tests and documentation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: tokenize Python source with PythonLexer and lex(). Required observable cases include python lexer keywords and names; get lexer by name returns python lexer; triple quoted string and operator tokens.
- **B002** — The extracted feature must support this observable behavior: resolve lexers by alias with get_lexer_by_name. Required observable cases include get lexer by name returns python lexer; triple quoted string and operator tokens.
- **B003** — The extracted feature must support this observable behavior: emit Token types for keywords, strings, comments, numbers, operators, and names. Required observable cases include string and comment tokens are distinct; triple quoted string and operator tokens.
- **B004** — The extracted feature must support this observable behavior: honor lexer options such as stripall and ensurenl. Required observable cases include stripall option removes whitespace tokens.
- **B005** — The extracted feature must support this observable behavior: support modeline and encoding helpers used by lexer lookup. Required observable cases include triple quoted string and operator tokens.
- **B006** — The package exposes the required task API paths `featurelifted.lex`, `featurelifted.get_lexer_by_name`, `featurelifted.PythonLexer`, `featurelifted.token`, `featurelifted.token.Comment`, `featurelifted.token.Keyword`, `featurelifted.token.Literal`, `featurelifted.token.Name`, `featurelifted.token.Number`, `featurelifted.token.Operator`, `featurelifted.token.String`, `featurelifted.token.Text`, and 6 listed members with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: pygments.
<!-- featureliftbench:behavior-clauses:end -->
