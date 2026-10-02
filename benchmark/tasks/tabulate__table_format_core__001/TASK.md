# FeatureLift Task: Table formatting core

Extract a task-scoped subset of `tabulate` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    simple_separated_format,
    tabulate,
    tabulate_formats,
)
```

## Required API Details

- `tabulate(tabular_data, headers=(), tablefmt='simple', floatfmt='g', intfmt='', numalign='default', stralign='default', missingval='', showindex='default', disable_numparse=False, colglobalalign=None, colalign=None, preserve_whitespace=False, maxcolwidths=None, headersglobalalign=None, headersalign=None, rowalign=None, maxheadercolwidths=None, break_long_words=True, break_on_hyphens=True)`
- `tabulate_formats` object must exist
- `simple_separated_format(separator)`

## Required Behavior

- The extracted feature must support this observable behavior: tabulate() renders simple, grid, pipe, and plain table formats. Required observable cases include tabulate simple ascii; tabulate with headers; tabulate grid basic; tabulate formats registry; wide char grid alignment; pipe format colalign; latex booktabs format; dict rows headers keys.
- The extracted feature must support this observable behavior: automatic numeric decimal alignment and string column padding. Required observable cases include decimal column alignment.
- The extracted feature must support this observable behavior: colalign and colglobalalign per-column alignment overrides. Required observable cases include decimal column alignment; colglobalalign center column.
- The extracted feature must support this observable behavior: Unicode wide-character display width via wcwidth when available. Required observable cases include wide char grid alignment.
- The extracted feature must support this observable behavior: ANSI escape sequences excluded from visible column width. Required observable cases include ansi visible width plain; html escapes angle brackets.
- The extracted feature must support this observable behavior: simple_separated_format builds custom separator TableFormat. Required observable cases include wide char grid alignment.
- The extracted feature must support this observable behavior: tabulate_formats lists supported output format names. Required observable cases include tabulate with headers; tabulate formats registry; latex booktabs format; dict rows headers keys.
- The package exposes the required task API paths `featurelifted.tabulate`, `featurelifted.tabulate_formats`, `featurelifted.simple_separated_format` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `tabulate`.
- Do not implement CLI entrypoint tabulate/cli.py and __main__.
- Do not implement upstream benchmark and example scripts.
- Do not implement original tabulate import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: tabulate() renders simple, grid, pipe, and plain table formats. Required observable cases include tabulate simple ascii; tabulate with headers; tabulate grid basic; tabulate formats registry; wide char grid alignment; pipe format colalign; latex booktabs format; dict rows headers keys.
- **B002** — The extracted feature must support this observable behavior: automatic numeric decimal alignment and string column padding. Required observable cases include decimal column alignment.
- **B003** — The extracted feature must support this observable behavior: colalign and colglobalalign per-column alignment overrides. Required observable cases include decimal column alignment; colglobalalign center column.
- **B004** — The extracted feature must support this observable behavior: Unicode wide-character display width via wcwidth when available. Required observable cases include wide char grid alignment.
- **B005** — The extracted feature must support this observable behavior: ANSI escape sequences excluded from visible column width. Required observable cases include ansi visible width plain; html escapes angle brackets.
- **B006** — The extracted feature must support this observable behavior: simple_separated_format builds custom separator TableFormat. Required observable cases include wide char grid alignment.
- **B007** — The extracted feature must support this observable behavior: tabulate_formats lists supported output format names. Required observable cases include tabulate with headers; tabulate formats registry; latex booktabs format; dict rows headers keys.
- **B008** — The package exposes the required task API paths `featurelifted.tabulate`, `featurelifted.tabulate_formats`, `featurelifted.simple_separated_format` with the kinds and callable signatures listed in this contract.
- **B009** — the submitted package does not import forbidden upstream packages: tabulate.
<!-- featureliftbench:behavior-clauses:end -->
