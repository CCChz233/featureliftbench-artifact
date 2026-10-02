# FeatureLift Task: ConfigBox dot-access config transforms

Extract a task-scoped subset of `box` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Box,
    ConfigBox,
    exceptions,
)
```

## Required API Details

- `Box(*args: 'Any', default_box: 'bool' = False, default_box_attr: 'Any' = <object object>, default_box_none_transform: 'bool' = True, default_box_create_on_get: 'bool' = True, frozen_box: 'bool' = False, camel_killer_box: 'bool' = False, conversion_box: 'bool' = True, modify_tuples_box: 'bool' = False, box_safe_prefix: 'str' = 'x', box_duplicates: 'str' = 'ignore', box_intact_types: 'tuple | list' = (), box_recast: 'dict | None' = None, box_dots: 'bool' = False, box_dots_exclude: 'str | None' = None, box_class: 'dict | type[Box] | None' = None, box_namespace: 'tuple[str, ...] | Literal[False]' = (), **kwargs: 'Any')` class constructor
- `ConfigBox(*args: 'Any', default_box: 'bool' = False, default_box_attr: 'Any' = <object object>, default_box_none_transform: 'bool' = True, default_box_create_on_get: 'bool' = True, frozen_box: 'bool' = False, camel_killer_box: 'bool' = False, conversion_box: 'bool' = True, modify_tuples_box: 'bool' = False, box_safe_prefix: 'str' = 'x', box_duplicates: 'str' = 'ignore', box_intact_types: 'tuple | list' = (), box_recast: 'dict | None' = None, box_dots: 'bool' = False, box_dots_exclude: 'str | None' = None, box_class: 'dict | type[Box] | None' = None, box_namespace: 'tuple[str, ...] | Literal[False]' = (), **kwargs: 'Any')` class constructor
  - `ConfigBox.bool(self, item, default=None)`
  - `ConfigBox.float(self, item, default=None)`
  - `ConfigBox.getboolean(self, item, default=None)`
  - `ConfigBox.getfloat(self, item, default=None)`
  - `ConfigBox.int(self, item, default=None)`
  - `ConfigBox.list(self, item, default=None, spliter: 'str' = ',', strip=True, mod=None)`
- `exceptions` module must be importable
  - `exceptions.BoxKeyError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: dot and bracket dict access. Required observable cases include dot access; no box import surface.
- The extracted feature must support this observable behavior: case-insensitive ConfigBox keys. Required observable cases include case insensitive key lookup; getboolean alias; missing key raises.
- The extracted feature must support this observable behavior: bool/int/float/list coercion helpers. Required observable cases include bool yes no; int coercion; list with mod callback; float and getfloat default.
- The extracted feature must support this observable behavior: default values on missing keys. Required observable cases include float and getfloat default; missing key raises.
- The package exposes the required task API paths `featurelifted.Box`, `featurelifted.ConfigBox`, `featurelifted.ConfigBox.bool`, `featurelifted.ConfigBox.float`, `featurelifted.ConfigBox.getboolean`, `featurelifted.ConfigBox.getfloat`, `featurelifted.ConfigBox.int`, `featurelifted.ConfigBox.list`, `featurelifted.exceptions`, `featurelifted.exceptions.BoxKeyError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `box`.
- Do not implement yaml/toml/msgpack converters and file loaders.
- Do not implement ShorthandBox and BoxList extras.
- Do not implement original box import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: dot and bracket dict access. Required observable cases include dot access; no box import surface.
- **B002** — The extracted feature must support this observable behavior: case-insensitive ConfigBox keys. Required observable cases include case insensitive key lookup; getboolean alias; missing key raises.
- **B003** — The extracted feature must support this observable behavior: bool/int/float/list coercion helpers. Required observable cases include bool yes no; int coercion; list with mod callback; float and getfloat default.
- **B004** — The extracted feature must support this observable behavior: default values on missing keys. Required observable cases include float and getfloat default; missing key raises.
- **B005** — The package exposes the required task API paths `featurelifted.Box`, `featurelifted.ConfigBox`, `featurelifted.ConfigBox.bool`, `featurelifted.ConfigBox.float`, `featurelifted.ConfigBox.getboolean`, `featurelifted.ConfigBox.getfloat`, `featurelifted.ConfigBox.int`, `featurelifted.ConfigBox.list`, `featurelifted.exceptions`, `featurelifted.exceptions.BoxKeyError` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: box.
<!-- featureliftbench:behavior-clauses:end -->
