# FeatureLift Task: LazyCommandCollection

Extract a task-scoped subset of `click` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Command,
    LazyCommandCollection,
    UsageError,
)
```

## Required API Details

- `LazyCommandCollection(sources: 'dict[str, Callable[[], Command]]', *, envvar: 'str | None' = None) -> 'None'` class constructor
  - `LazyCommandCollection.get_command(self, name: 'str') -> 'Command | None'`
  - `LazyCommandCollection.resolve(self, argv: 'list[str]') -> 'tuple[Context, Command, list[str]]'`
- `Command(name: 'str', callback: 'Callable[..., Any] | None' = None) -> 'None'` class constructor
- `UsageError` must be importable and raisable

## Required Behavior

- When a command name is requested, LazyCommandCollection loads only the source that supplies that command and caches the resolved command.
- When a context is created, collection defaults and envvar settings are propagated to command resolution without eagerly loading unrelated commands.
- When resolve receives argv, it returns the resolved Context, Command, and remaining arguments and raises UsageError for unknown commands.
- The package exposes the required task API paths `featurelifted.LazyCommandCollection`, `featurelifted.LazyCommandCollection.get_command`, `featurelifted.LazyCommandCollection.resolve`, `featurelifted.Command`, `featurelifted.UsageError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `click`.
- Forbidden path access: `repo/, click/`.
- Do not implement network access.
- Do not implement shell completion.
- Do not implement full CLI runner.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When a command name is requested, LazyCommandCollection loads only the source that supplies that command and caches the resolved command.
- **B002** — When a context is created, collection defaults and envvar settings are propagated to command resolution without eagerly loading unrelated commands.
- **B003** — When resolve receives argv, it returns the resolved Context, Command, and remaining arguments and raises UsageError for unknown commands.
- **B004** — The package exposes the required task API paths `featurelifted.LazyCommandCollection`, `featurelifted.LazyCommandCollection.get_command`, `featurelifted.LazyCommandCollection.resolve`, `featurelifted.Command`, `featurelifted.UsageError` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: click.
<!-- featureliftbench:behavior-clauses:end -->
