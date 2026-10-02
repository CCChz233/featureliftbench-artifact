# FeatureLift Task: HTML formatter core

Extract a task-scoped subset of `pygments` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    get_lexer_by_name,
    highlight,
    HtmlFormatter,
)
```

## Required API Details

- `highlight(code, lexer, formatter, outfile=None)`
- `HtmlFormatter(**options)` class constructor
- `get_lexer_by_name(_alias, **options)`

## Required Behavior

- The extracted feature must support this observable behavior: render token streams to HTML spans with HtmlFormatter. Required observable cases include html formatter wraps tokens; linenos and cssclass options.
- The extracted feature must support this observable behavior: highlight source with highlight(code, lexer, formatter). Required observable cases include full document and keyword highlighting.
- The extracted feature must support this observable behavior: support nowrap, linenos, cssclass, and title options. Required observable cases include nowrap option omits outer div; linenos and cssclass options.
- The extracted feature must support this observable behavior: escape HTML in source text and preserve token class names. Required observable cases include html formatter wraps tokens; html escapes angle brackets in source.
- The extracted feature must support this observable behavior: resolve Python lexer for integrated highlighting. Required observable cases include full document and keyword highlighting.
- The package exposes the required task API paths `featurelifted.highlight`, `featurelifted.HtmlFormatter`, `featurelifted.get_lexer_by_name` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pygments`.
- Do not implement image, LaTeX, RTF, SVG, and terminal formatters.
- Do not implement command-line pygmentize tool.
- Do not implement full lexer catalog beyond Python integration.
- Do not implement original project tests and documentation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: render token streams to HTML spans with HtmlFormatter. Required observable cases include html formatter wraps tokens; linenos and cssclass options.
- **B002** — The extracted feature must support this observable behavior: highlight source with highlight(code, lexer, formatter). Required observable cases include full document and keyword highlighting.
- **B003** — The extracted feature must support this observable behavior: support nowrap, linenos, cssclass, and title options. Required observable cases include nowrap option omits outer div; linenos and cssclass options.
- **B004** — The extracted feature must support this observable behavior: escape HTML in source text and preserve token class names. Required observable cases include html formatter wraps tokens; html escapes angle brackets in source.
- **B005** — The extracted feature must support this observable behavior: resolve Python lexer for integrated highlighting. Required observable cases include full document and keyword highlighting.
- **B006** — The package exposes the required task API paths `featurelifted.highlight`, `featurelifted.HtmlFormatter`, `featurelifted.get_lexer_by_name` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: pygments.
<!-- featureliftbench:behavior-clauses:end -->
