# FeatureLift Task: Jinja2 filters and tests core

Extract a task-scoped subset of `jinja2` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Environment,
    filters,
    runtime,
    tests,
)
```

## Required API Details

- `Environment(block_start_string: str = '{%', block_end_string: str = '%}', variable_start_string: str = '{{', variable_end_string: str = '}}', comment_start_string: str = '{#', comment_end_string: str = '#}', line_statement_prefix: Optional[str] = None, line_comment_prefix: Optional[str] = None, trim_blocks: bool = False, lstrip_blocks: bool = False, newline_sequence: "te.Literal['\\n', '\\r\\n', '\\r']" = '\n', keep_trailing_newline: bool = False, extensions: Sequence[Union[str, Type[ForwardRef('Extension')]]] = (), optimized: bool = True, undefined: Type[Undefined] = <class 'Undefined'>, finalize: Optional[Callable[..., Any]] = None, autoescape: Union[bool, Callable[[Optional[str]], bool]] = False, loader: Optional[ForwardRef('BaseLoader')] = None, cache_size: int = 400, auto_reload: bool = True, bytecode_cache: Optional[ForwardRef('BytecodeCache')] = None, enable_async: bool = False)` class constructor
  - `Environment.call_filter(self, name: str, value: Any, args: Optional[Sequence[Any]] = None, kwargs: Optional[Mapping[str, Any]] = None, context: Optional[Context] = None, eval_ctx: Optional[EvalContext] = None) -> Any`
  - `Environment.call_test(self, name: str, value: Any, args: Optional[Sequence[Any]] = None, kwargs: Optional[Mapping[str, Any]] = None, context: Optional[Context] = None, eval_ctx: Optional[EvalContext] = None) -> Any`
  - `Environment.from_string(self, source: Union[str, Template], globals: Optional[MutableMapping[str, Any]] = None, template_class: Optional[Type[ForwardRef('Template')]] = None) -> 'Template'`
- `filters` module must be importable
  - `filters.FILTERS` attribute must exist
- `tests` module must be importable
  - `tests.TESTS` attribute must exist
- `runtime` module must be importable
  - `runtime.Undefined(hint: Optional[str] = None, obj: Any = missing, name: Optional[str] = None, exc: Type[TemplateRuntimeError] = <class 'UndefinedError'>) -> None` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: apply built-in filters in templates and via call_filter. Required observable cases include capitalize filter in template; call filter directly; defined test in template.
- The extracted feature must support this observable behavior: evaluate built-in tests in templates and via call_test. Required observable cases include defined test in template.
- The extracted feature must support this observable behavior: support common filters: capitalize, default, length, join, map, select. Required observable cases include capitalize filter in template; default filter with boolean; filters module required for join.
- The extracted feature must support this observable behavior: support common tests: defined, undefined, even, odd, number, string. Required observable cases include tests module required for even.
- The extracted feature must support this observable behavior: default filter honors boolean true to treat falsey values as missing. Required observable cases include default filter with boolean.
- The extracted feature must support this observable behavior: runtime Undefined and filters/tests registries must be available for call_filter/call_test. Required observable cases include call filter directly; tests module required for even.
- The package exposes the required task API paths `featurelifted.Environment`, `featurelifted.Environment.call_filter`, `featurelifted.Environment.call_test`, `featurelifted.Environment.from_string`, `featurelifted.filters`, `featurelifted.filters.FILTERS`, `featurelifted.tests`, `featurelifted.tests.TESTS`, `featurelifted.runtime`, `featurelifted.runtime.Undefined` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `jinja2, jinja`.
- Do not implement custom extension filters.
- Do not implement async filter variants.
- Do not implement loaders and template inheritance beyond from_string.
- Do not implement CLI, original tests, docs, packaging metadata.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: apply built-in filters in templates and via call_filter. Required observable cases include capitalize filter in template; call filter directly; defined test in template.
- **B002** — The extracted feature must support this observable behavior: evaluate built-in tests in templates and via call_test. Required observable cases include defined test in template.
- **B003** — The extracted feature must support this observable behavior: support common filters: capitalize, default, length, join, map, select. Required observable cases include capitalize filter in template; default filter with boolean; filters module required for join.
- **B004** — The extracted feature must support this observable behavior: support common tests: defined, undefined, even, odd, number, string. Required observable cases include tests module required for even.
- **B005** — The extracted feature must support this observable behavior: default filter honors boolean true to treat falsey values as missing. Required observable cases include default filter with boolean.
- **B006** — The extracted feature must support this observable behavior: runtime Undefined and filters/tests registries must be available for call_filter/call_test. Required observable cases include call filter directly; tests module required for even.
- **B007** — The package exposes the required task API paths `featurelifted.Environment`, `featurelifted.Environment.call_filter`, `featurelifted.Environment.call_test`, `featurelifted.Environment.from_string`, `featurelifted.filters`, `featurelifted.filters.FILTERS`, `featurelifted.tests`, `featurelifted.tests.TESTS`, `featurelifted.runtime`, `featurelifted.runtime.Undefined` with the kinds and callable signatures listed in this contract.
- **B008** — the submitted package does not import forbidden upstream packages: jinja2, jinja.
<!-- featureliftbench:behavior-clauses:end -->
