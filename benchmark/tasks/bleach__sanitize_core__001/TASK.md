# FeatureLift Task: HTML sanitizer clean core

Extract a task-scoped subset of `bleach` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    ALLOWED_ATTRIBUTES,
    ALLOWED_PROTOCOLS,
    ALLOWED_TAGS,
    clean,
    Cleaner,
)
```

## Required API Details

- `clean(text, tags=['a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em', 'i', 'li', 'ol', 'strong', 'ul'], attributes={'a': ['href', 'title'], 'abbr': ['title'], 'acronym': ['title']}, styles=[], protocols=['http', 'https', 'mailto'], strip=False, strip_comments=True)`
- `Cleaner(tags=['a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em', 'i', 'li', 'ol', 'strong', 'ul'], attributes={'a': ['href', 'title'], 'abbr': ['title'], 'acronym': ['title']}, styles=[], protocols=['http', 'https', 'mailto'], strip=False, strip_comments=True, filters=None)` class constructor
- `ALLOWED_TAGS` constant must exist
- `ALLOWED_ATTRIBUTES` constant must exist
- `ALLOWED_PROTOCOLS` constant must exist

## Required Behavior

- The extracted feature must support this observable behavior: XSS tag stripping. Required observable cases include clean escapes unknown tags; javascript href stripped.
- The extracted feature must support this observable behavior: allowed attributes and protocols. Required observable cases include clean allows safe link; strip mode removes tag.
- The extracted feature must support this observable behavior: strip and strip_comments modes. Required observable cases include clean strips script; strip disallowed script; strip mode removes tag; strip comments removed.
- The extracted feature must support this observable behavior: callable attribute filters. Required observable cases include custom attributes callable.
- The package exposes the required task API paths `featurelifted.clean`, `featurelifted.Cleaner`, `featurelifted.ALLOWED_TAGS`, `featurelifted.ALLOWED_ATTRIBUTES`, `featurelifted.ALLOWED_PROTOCOLS` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `bleach`.
- Do not implement linkify.
- Do not implement upstream packaging.
- Do not implement original bleach import.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: XSS tag stripping. Required observable cases include clean escapes unknown tags; javascript href stripped.
- **B002** — The extracted feature must support this observable behavior: allowed attributes and protocols. Required observable cases include clean allows safe link; strip mode removes tag.
- **B003** — The extracted feature must support this observable behavior: strip and strip_comments modes. Required observable cases include clean strips script; strip disallowed script; strip mode removes tag; strip comments removed.
- **B004** — The extracted feature must support this observable behavior: callable attribute filters. Required observable cases include custom attributes callable.
- **B005** — The package exposes the required task API paths `featurelifted.clean`, `featurelifted.Cleaner`, `featurelifted.ALLOWED_TAGS`, `featurelifted.ALLOWED_ATTRIBUTES`, `featurelifted.ALLOWED_PROTOCOLS` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: bleach.
<!-- featureliftbench:behavior-clauses:end -->
