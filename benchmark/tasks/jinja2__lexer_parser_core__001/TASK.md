# FeatureLift Task: Jinja2 lexer and parser core

Extract a task-scoped subset of `jinja2` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Environment,
    lexer,
    nodes,
    parser,
)
```

## Required API Details

- `Environment(block_start_string: 'str' = '{%', block_end_string: 'str' = '%}', variable_start_string: 'str' = '{{', variable_end_string: 'str' = '}}', comment_start_string: 'str' = '{#', comment_end_string: 'str' = '#}', line_statement_prefix: 't.Optional[str]' = None, line_comment_prefix: 't.Optional[str]' = None, trim_blocks: 'bool' = False, lstrip_blocks: 'bool' = False, newline_sequence: '"te.Literal[\'\\\\n\', \'\\\\r\\\\n\', \'\\\\r\']"' = '\n', keep_trailing_newline: 'bool' = False) -> 'None'` class constructor
  - `Environment.parse(self, source: 'str', name: 't.Optional[str]' = None, filename: 't.Optional[str]' = None) -> 'nodes.Template'`
  - `Environment.lex(self, source: 'str', name: 't.Optional[str]' = None, filename: 't.Optional[str]' = None) -> 't.Iterator[t.Tuple[int, str, str]]'`
- `nodes` module must be importable
  - `nodes.For(*fields: Any, **attributes: Any) -> None` class constructor
  - `nodes.If(*fields: Any, **attributes: Any) -> None` class constructor
  - `nodes.Name(*fields: Any, **attributes: Any) -> None` class constructor
  - `nodes.Output(*fields: Any, **attributes: Any) -> None` class constructor
  - `nodes.Template(*fields: Any, **attributes: Any) -> None` class constructor
- `lexer` module must be importable
  - `lexer.Lexer(environment: 'Environment') -> None` class constructor
    - `lexer.Lexer.tokenize(self, source: str, name: Optional[str] = None, filename: Optional[str] = None, state: Optional[str] = None) -> TokenStream`
- `parser` module must be importable
  - `parser.Parser(environment: 'Environment', source: str, name: Optional[str] = None, filename: Optional[str] = None, state: Optional[str] = None) -> None` class constructor
    - `parser.Parser.parse(self) -> Template`

## Required Behavior

- The extracted feature must support this observable behavior: tokenize template source into token streams. Required observable cases include lex returns token types; parser module required for if elif.
- The extracted feature must support this observable behavior: parse templates into AST node trees. Required observable cases include parse variable output; parse for loop structure; parser module required for if elif.
- The extracted feature must support this observable behavior: support block, variable, comment, and statement delimiters. Required observable cases include lexer module required for raw blocks.
- The extracted feature must support this observable behavior: preserve syntax error reporting with line numbers. Required observable cases include parser module required for if elif.
- The package exposes the required task API paths `featurelifted.Environment`, `featurelifted.Environment.parse`, `featurelifted.Environment.lex`, `featurelifted.nodes`, `featurelifted.nodes.For`, `featurelifted.nodes.If`, `featurelifted.nodes.Name`, `featurelifted.nodes.Output`, `featurelifted.nodes.Template`, `featurelifted.lexer`, `featurelifted.lexer.Lexer`, `featurelifted.lexer.Lexer.tokenize`, and 3 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `jinja2, jinja`.
- Do not implement template compilation and rendering.
- Do not implement loaders and template inheritance.
- Do not implement filters, tests, extensions, async mode.
- Do not implement CLI, original tests, docs, packaging metadata.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: tokenize template source into token streams. Required observable cases include lex returns token types; parser module required for if elif.
- **B002** — The extracted feature must support this observable behavior: parse templates into AST node trees. Required observable cases include parse variable output; parse for loop structure; parser module required for if elif.
- **B003** — The extracted feature must support this observable behavior: support block, variable, comment, and statement delimiters. Required observable cases include lexer module required for raw blocks.
- **B004** — The extracted feature must support this observable behavior: preserve syntax error reporting with line numbers. Required observable cases include parser module required for if elif.
- **B005** — The package exposes the required task API paths `featurelifted.Environment`, `featurelifted.Environment.parse`, `featurelifted.Environment.lex`, `featurelifted.nodes`, `featurelifted.nodes.For`, `featurelifted.nodes.If`, `featurelifted.nodes.Name`, `featurelifted.nodes.Output`, `featurelifted.nodes.Template`, `featurelifted.lexer`, `featurelifted.lexer.Lexer`, `featurelifted.lexer.Lexer.tokenize`, and 3 listed members with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: jinja2, jinja.
<!-- featureliftbench:behavior-clauses:end -->
