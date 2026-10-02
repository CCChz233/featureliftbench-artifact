# FeatureLift Task: JSON Pointer resolve and set

Extract a task-scoped subset of `jsonpointer` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    EndOfList,
    escape,
    JsonPointer,
    JsonPointerException,
    resolve_pointer,
    set_pointer,
    unescape,
)
```

## Required API Details

- `EndOfList(list_) -> None` class constructor
- `JsonPointer(pointer)` class constructor
  - `JsonPointer.from_parts(parts)`
  - `JsonPointer.get_parts(self)`
  - `JsonPointer.path` attribute must exist on instances
  - `JsonPointer.__contains__(self, item)`
- `JsonPointerException` must be importable and raisable
- `resolve_pointer(doc, pointer, default=<object object>)`
- `set_pointer(doc, pointer, value, inplace=True)`
- `escape(s: str) -> str`
- `unescape(s: str) -> str`

## Required Behavior

- The extracted feature must support this observable behavior: resolve pointers against nested dict/list documents. Required observable cases include resolve root empty pointer; resolve nested dict path; resolve array index; set pointer inplace; json pointer path round trip; end of list marker; pointer join operator.
- The extracted feature must support this observable behavior: set values including array append via '-' token. Required observable cases include resolve array index; set pointer inplace; array index rejects leading zero; set append via dash; set out of place deepcopy.
- The extracted feature must support this observable behavior: escape and unescape ~ and / in token names. Required observable cases include escape round trip paths.
- The extracted feature must support this observable behavior: default values for missing paths and invalid escapes. Required observable cases include json pointer path round trip; escape round trip paths; invalid escape raises; resolve missing with default.
- The package exposes the required task API paths `featurelifted.EndOfList`, `featurelifted.JsonPointer`, `featurelifted.JsonPointer.from_parts`, `featurelifted.JsonPointer.get_parts`, `featurelifted.JsonPointer.path`, `featurelifted.JsonPointer.__contains__`, `featurelifted.JsonPointerException`, `featurelifted.resolve_pointer`, `featurelifted.set_pointer`, `featurelifted.escape`, `featurelifted.unescape` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `jsonpointer`.
- Do not implement jsonpatch operations beyond pointer resolve/set.
- Do not implement upstream tests and docs.
- Do not implement original jsonpointer import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: resolve pointers against nested dict/list documents. Required observable cases include resolve root empty pointer; resolve nested dict path; resolve array index; set pointer inplace; json pointer path round trip; end of list marker; pointer join operator.
- **B002** — The extracted feature must support this observable behavior: set values including array append via '-' token. Required observable cases include resolve array index; set pointer inplace; array index rejects leading zero; set append via dash; set out of place deepcopy.
- **B003** — The extracted feature must support this observable behavior: escape and unescape ~ and / in token names. Required observable cases include escape round trip paths.
- **B004** — The extracted feature must support this observable behavior: default values for missing paths and invalid escapes. Required observable cases include json pointer path round trip; escape round trip paths; invalid escape raises; resolve missing with default.
- **B005** — The package exposes the required task API paths `featurelifted.EndOfList`, `featurelifted.JsonPointer`, `featurelifted.JsonPointer.from_parts`, `featurelifted.JsonPointer.get_parts`, `featurelifted.JsonPointer.path`, `featurelifted.JsonPointer.__contains__`, `featurelifted.JsonPointerException`, `featurelifted.resolve_pointer`, `featurelifted.set_pointer`, `featurelifted.escape`, `featurelifted.unescape` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: jsonpointer.
<!-- featureliftbench:behavior-clauses:end -->
