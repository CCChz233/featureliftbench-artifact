# FeatureLift Task: render_readme

Extract a task-scoped subset of `readme_renderer` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    render_readme,
)
```

## Required API Details

- `render_readme(content: 'str', content_type: 'str') -> 'tuple[str, list[str]]'`

## Required Behavior

- `render_readme(content, content_type)` selects plain, markdown, or reST renderers.
- Unknown media types fall back to plain text with warnings.
- Unsupported charset parameters produce warnings.
- The package exposes the required task API paths `featurelifted.render_readme` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `readme_renderer`.
- Forbidden path access: `repo/, readme_renderer/`.
- Do not implement network access.
- Do not implement full docutils/markdown optional deps.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `render_readme(content, content_type)` selects plain, markdown, or reST renderers.
- **B002** — Unknown media types fall back to plain text with warnings.
- **B003** — Unsupported charset parameters produce warnings.
- **B004** — The package exposes the required task API paths `featurelifted.render_readme` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: readme_renderer.
<!-- featureliftbench:behavior-clauses:end -->
