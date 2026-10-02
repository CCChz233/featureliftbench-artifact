# FeatureLift Task: CLDR plural rules subset

Extract a task-scoped subset of `babel` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Locale,
    PluralRule,
)
```

## Required API Details

- `PluralRule(rules)` class constructor
  - `PluralRule.parse(rules)`
- `Locale(language, territory=None, script=None, variant=None)` class constructor
  - `Locale.parse(identifier, sep='_', resolve_likely_subtags=True)`
  - `Locale.plural_form` attribute must exist on instances

## Required Behavior

- The extracted feature must support this observable behavior: evaluate PluralRule expressions for numeric operands. Required observable cases include plural rule string and float operands.
- The extracted feature must support this observable behavior: resolve Locale plural categories for en, ru, fr, ja, and pl. Required observable cases include locale plural categories multilingual.
- The extracted feature must support this observable behavior: load plural rules from packaged locale-data .dat resources. Required observable cases include plural rule and english locale; plural rule expression edges; plural rule string and float operands.
- The package exposes the required task API paths `featurelifted.PluralRule`, `featurelifted.PluralRule.parse`, `featurelifted.Locale`, `featurelifted.Locale.parse`, `featurelifted.Locale.plural_form` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `babel`.
- Do not implement gettext message catalogs and extraction.
- Do not implement number/date/currency formatting modules.
- Do not implement full CLDR locale-data tree.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: evaluate PluralRule expressions for numeric operands. Required observable cases include plural rule string and float operands.
- **B002** — The extracted feature must support this observable behavior: resolve Locale plural categories for en, ru, fr, ja, and pl. Required observable cases include locale plural categories multilingual.
- **B003** — The extracted feature must support this observable behavior: load plural rules from packaged locale-data .dat resources. Required observable cases include plural rule and english locale; plural rule expression edges; plural rule string and float operands.
- **B004** — The package exposes the required task API paths `featurelifted.PluralRule`, `featurelifted.PluralRule.parse`, `featurelifted.Locale`, `featurelifted.Locale.parse`, `featurelifted.Locale.plural_form` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: babel.
<!-- featureliftbench:behavior-clauses:end -->
