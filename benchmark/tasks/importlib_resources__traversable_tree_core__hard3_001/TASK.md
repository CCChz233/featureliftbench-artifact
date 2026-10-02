# FeatureLift Task: Traversable resource tree and text/binary reader

Extract a task-scoped subset of `importlib_resources` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    files,
    MemoryTraversable,
    read_binary,
    read_text,
    TraversalError,
)
```

## Required API Details

- `TraversalError` must be importable and raisable
- `files(anchor: 'types.ModuleType | str | MemoryTraversable') -> 'FileTraversable | MemoryTraversable'`
- `read_binary(anchor: 'types.ModuleType | str | MemoryTraversable', resource: 'str') -> 'bytes'`
- `read_text(anchor: 'types.ModuleType | str | MemoryTraversable', resource: 'str', encoding: 'str' = 'utf-8', errors: 'str' = 'strict') -> 'str'`
- `MemoryTraversable(name: 'str', children: "dict[str, 'MemoryTraversable'] | None" = None, data: 'bytes | None' = None) -> 'None'` class constructor
  - `MemoryTraversable.directory(name: 'str', entries: 'dict[str, Any]') -> "'MemoryTraversable'"`
  - `MemoryTraversable.joinpath(self, *descendants: 'Any') -> "'MemoryTraversable'"`

## Required Behavior

- When files receives a module object or importable module-name string, it resolves the same package anchor.
- For filesystem packages, files returns a Traversable rooted at the package directory with stable child names.
- For in-memory package trees, MemoryTraversable exposes the same directory, file, open, and read operations as filesystem-backed traversables.
- Traversable nodes report name, is_file, and is_dir and implement iterdir, open, read_bytes, and read_text consistently.
- joinpath and the slash operator traverse child resources while preventing escape above the package root.
- read_text honors the requested encoding and read_binary returns the resource bytes unchanged.
- Parent traversal and missing-resource reads raise TraversalError instead of accessing paths outside the declared resource tree.
- The package exposes the required task API paths `featurelifted.TraversalError`, `featurelifted.files`, `featurelifted.read_binary`, `featurelifted.read_text`, `featurelifted.MemoryTraversable`, `featurelifted.MemoryTraversable.directory`, `featurelifted.MemoryTraversable.joinpath` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `importlib_resources`.
- Forbidden path access: `repo/, importlib_resources/`.
- Do not implement network access.
- Do not implement original repository import at runtime.
- Do not implement source repo path access.
- Do not implement zip importer adapters.
- Do not implement as_file temporary extraction.
- Do not implement deprecated contents/path helpers.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When files receives a module object or importable module-name string, it resolves the same package anchor.
- **B002** — For filesystem packages, files returns a Traversable rooted at the package directory with stable child names.
- **B003** — For in-memory package trees, MemoryTraversable exposes the same directory, file, open, and read operations as filesystem-backed traversables.
- **B004** — Traversable nodes report name, is_file, and is_dir and implement iterdir, open, read_bytes, and read_text consistently.
- **B005** — joinpath and the slash operator traverse child resources while preventing escape above the package root.
- **B006** — read_text honors the requested encoding and read_binary returns the resource bytes unchanged.
- **B007** — Parent traversal and missing-resource reads raise TraversalError instead of accessing paths outside the declared resource tree.
- **B008** — The package exposes the required task API paths `featurelifted.TraversalError`, `featurelifted.files`, `featurelifted.read_binary`, `featurelifted.read_text`, `featurelifted.MemoryTraversable`, `featurelifted.MemoryTraversable.directory`, `featurelifted.MemoryTraversable.joinpath` with the kinds and callable signatures listed in this contract.
- **B009** — the submitted package does not import forbidden upstream packages: importlib_resources.
<!-- featureliftbench:behavior-clauses:end -->
