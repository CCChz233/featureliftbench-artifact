# FeatureLift Task: Markdown tables and footnotes extensions

Extract a task-scoped subset of `markdown` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Markdown,
    markdown,
)
```

## Required API Details

- `markdown(text, **kwargs)`
- `Markdown(**kwargs)` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: pipe table rendering. Required observable cases include simple table; table header align; table row span.
- The extracted feature must support this observable behavior: footnote reference and backlink HTML. Required observable cases include basic footnote; footnote backlink; multiple footnotes order.
- The extracted feature must support this observable behavior: extension registration on Markdown class. Required observable cases include table row span.
- The package exposes the required task API paths `featurelifted.markdown`, `featurelifted.Markdown` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `markdown`.
- Do not implement unrelated extensions.
- Do not implement CLI __main__.
- Do not implement original markdown import.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: pipe table rendering. Required observable cases include simple table; table header align; table row span.
- **B002** — The extracted feature must support this observable behavior: footnote reference and backlink HTML. Required observable cases include basic footnote; footnote backlink; multiple footnotes order.
- **B003** — The extracted feature must support this observable behavior: extension registration on Markdown class. Required observable cases include table row span.
- **B004** — The package exposes the required task API paths `featurelifted.markdown`, `featurelifted.Markdown` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: markdown.
<!-- featureliftbench:behavior-clauses:end -->
