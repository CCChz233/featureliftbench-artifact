# FeatureLift Task: attrs field validators

Extract a task-scoped subset of `attrs` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    define,
    field,
    validate,
    validators,
)
```

## Required API Details

- `define(maybe_cls=None, *, these=None, repr=None, unsafe_hash=None, hash=None, init=None, slots=True, frozen=False, weakref_slot=True, str=False, auto_attribs=None, kw_only=False, cache_hash=False, auto_exc=True, eq=None, order=False, auto_detect=True, getstate_setstate=None, on_setattr=None, field_transformer=None, match_args=True)`
- `field(*, default=NOTHING, validator=None, repr=True, hash=None, init=True, metadata=None, type=None, converter=None, factory=None, kw_only=False, eq=None, order=None, on_setattr=None, alias=None)`
- `validate(inst)`
- `validators` module must be importable
  - `validators.and_(*validators)`
  - `validators.deep_iterable(member_validator, iterable_validator=None)`
  - `validators.deep_mapping(key_validator, value_validator, mapping_validator=None)`
  - `validators.ge(val)`
  - `validators.instance_of(type)`
  - `validators.matches_re(regex, flags=0, func=None)`
  - `validators.min_len(length)`
  - `validators.optional(validator)`
  - `validators.set_disabled(disabled)`

## Required Behavior

- The extracted feature must support this observable behavior: attach validators to fields on define() classes. Required observable cases include set disabled skips validation.
- The extracted feature must support this observable behavior: run instance_of, ge, lt, matches_re, in_, and length validators. Required observable cases include valid instance passes; instance of rejects wrong type; matches re and deep iterable.
- The extracted feature must support this observable behavior: compose validators with and_, not_, and optional. Required observable cases include set disabled skips validation.
- The extracted feature must support this observable behavior: validate deep_iterable and deep_mapping structures. Required observable cases include matches re and deep iterable; deep mapping validates keys and values; optional allows none and validates present values.
- The extracted feature must support this observable behavior: globally disable validators with set_disabled and validate(). Required observable cases include optional allows none and validates present values; set disabled skips validation.
- The package exposes the required task API paths `featurelifted.define`, `featurelifted.field`, `featurelifted.validate`, `featurelifted.validators`, `featurelifted.validators.and_`, `featurelifted.validators.deep_iterable`, `featurelifted.validators.deep_mapping`, `featurelifted.validators.ge`, `featurelifted.validators.instance_of`, `featurelifted.validators.matches_re`, `featurelifted.validators.min_len`, `featurelifted.validators.optional`, and 1 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `attrs, attr`.
- Do not implement cmp, converters beyond validator helpers, and custom setters.
- Do not implement asdict, astuple, and serialization helpers.
- Do not implement original project tests and documentation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: attach validators to fields on define() classes. Required observable cases include set disabled skips validation.
- **B002** — The extracted feature must support this observable behavior: run instance_of, ge, lt, matches_re, in_, and length validators. Required observable cases include valid instance passes; instance of rejects wrong type; matches re and deep iterable.
- **B003** — The extracted feature must support this observable behavior: compose validators with and_, not_, and optional. Required observable cases include set disabled skips validation.
- **B004** — The extracted feature must support this observable behavior: validate deep_iterable and deep_mapping structures. Required observable cases include matches re and deep iterable; deep mapping validates keys and values; optional allows none and validates present values.
- **B005** — The extracted feature must support this observable behavior: globally disable validators with set_disabled and validate(). Required observable cases include optional allows none and validates present values; set disabled skips validation.
- **B006** — The package exposes the required task API paths `featurelifted.define`, `featurelifted.field`, `featurelifted.validate`, `featurelifted.validators`, `featurelifted.validators.and_`, `featurelifted.validators.deep_iterable`, `featurelifted.validators.deep_mapping`, `featurelifted.validators.ge`, `featurelifted.validators.instance_of`, `featurelifted.validators.matches_re`, `featurelifted.validators.min_len`, `featurelifted.validators.optional`, and 1 listed members with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: attrs, attr.
<!-- featureliftbench:behavior-clauses:end -->
