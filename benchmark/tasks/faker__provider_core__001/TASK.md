# FeatureLift Task: Single-locale Faker providers

Extract a task-scoped subset of `faker` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Faker,
)
```

## Required API Details

- `Faker(locale: 'str | Sequence[str] | dict[str, int | float] | None' = None, providers: 'list[str] | None' = None, generator: 'Generator | None' = None, includes: 'list[str] | None' = None, use_weighting: 'bool' = True, **config: 'Any') -> 'None'` class constructor
  - `Faker.address() -> str`
  - `Faker.first_name() -> str`
  - `Faker.last_name() -> str`
  - `Faker.phone_number() -> str`
  - `Faker.seed_instance(self, seed: 'SeedType | None' = None) -> 'None'`

## Required Behavior

- The extracted feature must support this observable behavior: construct Faker with locale en_US and default person/address/phone providers. Required observable cases include en us person address and phone are seeded; only en us locale and provider formats; address contains city state zip pattern.
- The extracted feature must support this observable behavior: generate deterministic fake names, addresses, and phone numbers with seed_instance. Required observable cases include only en us locale and provider formats.
- The extracted feature must support this observable behavior: resolve localized provider modules and locale resource data. Required observable cases include only en us locale and provider formats.
- The package exposes the required task API paths `featurelifted.Faker`, `featurelifted.Faker.address`, `featurelifted.Faker.first_name`, `featurelifted.Faker.last_name`, `featurelifted.Faker.phone_number`, `featurelifted.Faker.seed_instance` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `faker`.
- Do not implement multi-locale weighting and proxy locale switching.
- Do not implement CLI, pytest plugin, and documentation.
- Do not implement providers beyond person, address, and phone_number.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: construct Faker with locale en_US and default person/address/phone providers. Required observable cases include en us person address and phone are seeded; only en us locale and provider formats; address contains city state zip pattern.
- **B002** — The extracted feature must support this observable behavior: generate deterministic fake names, addresses, and phone numbers with seed_instance. Required observable cases include only en us locale and provider formats.
- **B003** — The extracted feature must support this observable behavior: resolve localized provider modules and locale resource data. Required observable cases include only en us locale and provider formats.
- **B004** — The package exposes the required task API paths `featurelifted.Faker`, `featurelifted.Faker.address`, `featurelifted.Faker.first_name`, `featurelifted.Faker.last_name`, `featurelifted.Faker.phone_number`, `featurelifted.Faker.seed_instance` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: faker.
<!-- featureliftbench:behavior-clauses:end -->
