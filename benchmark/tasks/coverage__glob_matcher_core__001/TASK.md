# FeatureLift Task: Glob matcher core

Extract a task-scoped subset of `coverage` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    exceptions,
    GlobMatcher,
    globs_to_regex,
    prep_patterns,
)
```

## Required API Details

- `GlobMatcher(pats: 'Iterable[str]', name: 'str' = 'unknown') -> 'None'` class constructor
  - `GlobMatcher.match(self, fpath: 'str') -> 'bool'`
- `prep_patterns(patterns: 'Iterable[str]') -> 'list[str]'`
- `globs_to_regex(patterns: 'Iterable[str]', case_insensitive: 'bool' = False, partial: 'bool' = False) -> 're.Pattern[str]'`
- `exceptions` module must be importable
  - `exceptions.ConfigError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: prepare relative and absolute glob patterns for matching. Required observable cases include glob matcher matches simple patterns; prep patterns adds absolute path; glob matcher many patterns; glob matcher backslash pattern; glob matcher question mark single char.
- The extracted feature must support this observable behavior: match file paths against include/omit style glob lists. Required observable cases include glob matcher respects windows style paths; glob matcher question mark single char.
- The extracted feature must support this observable behavior: convert glob syntax to compiled regex with Windows slash tolerance. Required observable cases include glob matcher respects windows style paths.
- The extracted feature must support this observable behavior: reject invalid glob patterns such as triple-star segments. Required observable cases include glob matcher matches simple patterns; globs to regex rejects invalid pattern; glob matcher many patterns; glob matcher backslash pattern.
- The package exposes the required task API paths `featurelifted.GlobMatcher`, `featurelifted.GlobMatcher.match`, `featurelifted.prep_patterns`, `featurelifted.globs_to_regex`, `featurelifted.exceptions`, `featurelifted.exceptions.ConfigError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `coverage`.
- Do not implement path alias remapping for combine.
- Do not implement source/include/omit selection policy.
- Do not implement configuration file parsing.
- Do not implement coverage measurement, reporting, and CLI.
- Do not implement original project tests and packaging metadata.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: prepare relative and absolute glob patterns for matching. Required observable cases include glob matcher matches simple patterns; prep patterns adds absolute path; glob matcher many patterns; glob matcher backslash pattern; glob matcher question mark single char.
- **B002** — The extracted feature must support this observable behavior: match file paths against include/omit style glob lists. Required observable cases include glob matcher respects windows style paths; glob matcher question mark single char.
- **B003** — The extracted feature must support this observable behavior: convert glob syntax to compiled regex with Windows slash tolerance. Required observable cases include glob matcher respects windows style paths.
- **B004** — The extracted feature must support this observable behavior: reject invalid glob patterns such as triple-star segments. Required observable cases include glob matcher matches simple patterns; globs to regex rejects invalid pattern; glob matcher many patterns; glob matcher backslash pattern.
- **B005** — The package exposes the required task API paths `featurelifted.GlobMatcher`, `featurelifted.GlobMatcher.match`, `featurelifted.prep_patterns`, `featurelifted.globs_to_regex`, `featurelifted.exceptions`, `featurelifted.exceptions.ConfigError` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: coverage.
<!-- featureliftbench:behavior-clauses:end -->
