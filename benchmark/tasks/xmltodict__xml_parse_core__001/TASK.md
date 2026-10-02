# FeatureLift Task: XML parse and unparse core

Extract a task-scoped subset of `xmltodict` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    parse,
    ParsingInterrupted,
    unparse,
)
```

## Required API Details

- `parse` module must be importable
- `unparse` module must be importable
- `ParsingInterrupted` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: parse XML strings into ordered dicts with @ attribute prefix. Required observable cases include simple parse text node; parse attributes default prefix; parse repeated siblings become list; roundtrip simple document; custom attr prefix parse.
- The extracted feature must support this observable behavior: unparse dicts back to XML with matching attr_prefix and cdata_key. Required observable cases include unparse simple element; roundtrip simple document; unparse custom attr prefix roundtrip.
- The extracted feature must support this observable behavior: duplicate sibling elements become lists. Required observable cases include parse repeated siblings become list; unparse custom attr prefix roundtrip.
- The extracted feature must support this observable behavior: process_namespaces with optional namespace URI collapse map. Required observable cases include namespace collapse map.
- The extracted feature must support this observable behavior: mixed content via #text alongside child elements. Required observable cases include simple parse text node; unparse simple element; semi structured mixed content; force cdata wraps text nodes.
- The extracted feature must support this observable behavior: custom attr_prefix and cdata_key options. Required observable cases include custom attr prefix parse; unparse custom attr prefix roundtrip; force cdata wraps text nodes.
- The package exposes the required task API paths `featurelifted.parse`, `featurelifted.unparse`, `featurelifted.ParsingInterrupted` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `xmltodict`.
- Do not implement streaming item_depth callbacks and ParsingInterrupted control flow.
- Do not implement postprocessor hooks and force_list / force_cdata selectors.
- Do not implement process_comments and comment_key emission.
- Do not implement CLI marshal streaming entrypoint.
- Do not implement original xmltodict import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse XML strings into ordered dicts with @ attribute prefix. Required observable cases include simple parse text node; parse attributes default prefix; parse repeated siblings become list; roundtrip simple document; custom attr prefix parse.
- **B002** — The extracted feature must support this observable behavior: unparse dicts back to XML with matching attr_prefix and cdata_key. Required observable cases include unparse simple element; roundtrip simple document; unparse custom attr prefix roundtrip.
- **B003** — The extracted feature must support this observable behavior: duplicate sibling elements become lists. Required observable cases include parse repeated siblings become list; unparse custom attr prefix roundtrip.
- **B004** — The extracted feature must support this observable behavior: process_namespaces with optional namespace URI collapse map. Required observable cases include namespace collapse map.
- **B005** — The extracted feature must support this observable behavior: mixed content via #text alongside child elements. Required observable cases include simple parse text node; unparse simple element; semi structured mixed content; force cdata wraps text nodes.
- **B006** — The extracted feature must support this observable behavior: custom attr_prefix and cdata_key options. Required observable cases include custom attr prefix parse; unparse custom attr prefix roundtrip; force cdata wraps text nodes.
- **B007** — The package exposes the required task API paths `featurelifted.parse`, `featurelifted.unparse`, `featurelifted.ParsingInterrupted` with the kinds and callable signatures listed in this contract.
- **B008** — the submitted package does not import forbidden upstream packages: xmltodict.
<!-- featureliftbench:behavior-clauses:end -->
