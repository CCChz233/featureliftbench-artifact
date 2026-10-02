# FeatureLift Task: JSON Schema $ref resolution

Extract a task-scoped subset of `referencing` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    exceptions,
    jsonschema,
    Registry,
    Resource,
)
```

## Required API Details

- `Registry(resources=HashTrieMap({}), anchors: 'HashTrieMap[tuple[URI, str], AnchorType[D]]' = HashTrieMap({}), uncrawled: 'HashTrieSet[URI]' = HashTrieSet({}), retrieve: 'Retrieve[D]' = <function _fail_to_retrieve>) -> None` class constructor
  - `Registry.resolver(self, base_uri: 'URI' = '') -> 'Resolver[D]'`
  - `Registry.with_resource(self, uri: 'URI', resource: 'Resource[D]')`
  - `Registry.with_resources(self, pairs: 'Iterable[tuple[URI, Resource[D]]]') -> 'Registry[D]'`
- `Resource(contents: 'D', specification: 'Specification[D]') -> None` class constructor
  - `Resource.from_contents(contents: 'D', default_specification: 'Specification[D]' = None) -> 'Resource[D]'`
- `exceptions` module must be importable
  - `exceptions.NoSuchAnchor` must be importable and raisable
  - `exceptions.Unresolvable` must be importable and raisable
- `jsonschema` module must be importable
  - `jsonschema.DRAFT202012` constant must exist
  - `jsonschema.UnknownDialect` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: Registry resource registration and base URI resolution. Required observable cases include external ref resolution; unresolvable external ref.
- The extracted feature must support this observable behavior: $ref pointer and external URI chaining. Required observable cases include external ref resolution; fragment ref into defs; unresolvable external ref.
- The extracted feature must support this observable behavior: $anchor and JSON Schema dialect specifications. Required observable cases include anchor lookup; unknown dialect and missing anchor.
- The extracted feature must support this observable behavior: typed unresolvable and unknown dialect errors. Required observable cases include unknown dialect and missing anchor.
- The package exposes the required task API paths `featurelifted.Registry`, `featurelifted.Registry.resolver`, `featurelifted.Registry.with_resource`, `featurelifted.Registry.with_resources`, `featurelifted.Resource`, `featurelifted.Resource.from_contents`, `featurelifted.exceptions`, `featurelifted.exceptions.NoSuchAnchor`, `featurelifted.exceptions.Unresolvable`, `featurelifted.jsonschema`, `featurelifted.jsonschema.DRAFT202012`, `featurelifted.jsonschema.UnknownDialect` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `referencing`.
- Do not implement jsonschema validation keyword implementations.
- Do not implement network retrieval of remote schemas.
- Do not implement referencing test suite and original package import.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: Registry resource registration and base URI resolution. Required observable cases include external ref resolution; unresolvable external ref.
- **B002** — The extracted feature must support this observable behavior: $ref pointer and external URI chaining. Required observable cases include external ref resolution; fragment ref into defs; unresolvable external ref.
- **B003** — The extracted feature must support this observable behavior: $anchor and JSON Schema dialect specifications. Required observable cases include anchor lookup; unknown dialect and missing anchor.
- **B004** — The extracted feature must support this observable behavior: typed unresolvable and unknown dialect errors. Required observable cases include unknown dialect and missing anchor.
- **B005** — The package exposes the required task API paths `featurelifted.Registry`, `featurelifted.Registry.resolver`, `featurelifted.Registry.with_resource`, `featurelifted.Registry.with_resources`, `featurelifted.Resource`, `featurelifted.Resource.from_contents`, `featurelifted.exceptions`, `featurelifted.exceptions.NoSuchAnchor`, `featurelifted.exceptions.Unresolvable`, `featurelifted.jsonschema`, `featurelifted.jsonschema.DRAFT202012`, `featurelifted.jsonschema.UnknownDialect` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: referencing.
<!-- featureliftbench:behavior-clauses:end -->
