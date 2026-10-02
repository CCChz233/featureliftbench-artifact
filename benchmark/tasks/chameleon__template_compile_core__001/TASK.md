# FeatureLift Task: ZPT template compile and render

Extract a task-scoped subset of `chameleon` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    TemplateError,
    zpt,
)
```

## Required API Details

- `TemplateError` must be importable and raisable
- `zpt.template` module must be importable
  - `zpt.template.PageTemplate(body: 'bytes | str', **config: 'Unpack[PageTemplateConfig]')` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: compile and render PageTemplate from source strings. Required observable cases include render tal content; render python expression; tal replace marker.
- The extracted feature must support this observable behavior: TAL attributes content/repeat/condition. Required observable cases include render tal content; tal repeat and condition; tal attributes replace; tal replace marker.
- The extracted feature must support this observable behavior: TALES path and python expressions. Required observable cases include render python expression; tal replace marker.
- The extracted feature must support this observable behavior: macro define/use via metal namespace. Required observable cases include tal replace marker.
- The package exposes the required task API paths `featurelifted.TemplateError`, `featurelifted.zpt.template`, `featurelifted.zpt.template.PageTemplate` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `chameleon`.
- Do not implement filesystem PageTemplateFile loader and auto_reload.
- Do not implement i18n translation catalogs beyond defaults.
- Do not implement benchmark utilities and legacy loader paths.
- Do not implement original chameleon import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: compile and render PageTemplate from source strings. Required observable cases include render tal content; render python expression; tal replace marker.
- **B002** — The extracted feature must support this observable behavior: TAL attributes content/repeat/condition. Required observable cases include render tal content; tal repeat and condition; tal attributes replace; tal replace marker.
- **B003** — The extracted feature must support this observable behavior: TALES path and python expressions. Required observable cases include render python expression; tal replace marker.
- **B004** — The extracted feature must support this observable behavior: macro define/use via metal namespace. Required observable cases include tal replace marker.
- **B005** — The package exposes the required task API paths `featurelifted.TemplateError`, `featurelifted.zpt.template`, `featurelifted.zpt.template.PageTemplate` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: chameleon.
<!-- featureliftbench:behavior-clauses:end -->
