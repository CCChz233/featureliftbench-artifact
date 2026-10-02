# FeatureLift Task: Jinja2 extension loading

Extract a task-scoped subset of `jinja2` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Environment,
    ext,
    Extension,
    nodes,
)
```

## Required API Details

- `Environment(block_start_string: str = '{%', block_end_string: str = '%}', variable_start_string: str = '{{', variable_end_string: str = '}}', comment_start_string: str = '{#', comment_end_string: str = '#}', line_statement_prefix: Optional[str] = None, line_comment_prefix: Optional[str] = None, trim_blocks: bool = False, lstrip_blocks: bool = False, newline_sequence: "te.Literal['\\n', '\\r\\n', '\\r']" = '\n', keep_trailing_newline: bool = False, extensions: Sequence[Union[str, Type[ForwardRef('Extension')]]] = (), optimized: bool = True, undefined: Type[Undefined] = <class 'Undefined'>, finalize: Optional[Callable[..., Any]] = None, autoescape: Union[bool, Callable[[Optional[str]], bool]] = False, loader: Optional[ForwardRef('BaseLoader')] = None, cache_size: int = 400, auto_reload: bool = True, bytecode_cache: Optional[ForwardRef('BytecodeCache')] = None, enable_async: bool = False)` class constructor
  - `Environment.from_string(self, source: Union[str, Template], globals: Optional[MutableMapping[str, Any]] = None, template_class: Optional[Type[ForwardRef('Template')]] = None) -> 'Template'`
  - `Environment.iter_extensions(self) -> Iterator[ForwardRef('Extension')]`
- `Extension(environment: Environment) -> None` class constructor
- `nodes` module must be importable
  - `nodes.CallBlock(*fields: Any, **attributes: Any) -> None` class constructor
- `ext` module must be importable
  - `ext.do(environment: Environment) -> None`
  - `ext.loopcontrols(environment: Environment) -> None`

## Required Behavior

- The extracted feature must support this observable behavior: load extensions by import path string or Extension subclass. Required observable cases include preprocess extension rewrites delimiters.
- The extracted feature must support this observable behavior: register extension tags and preprocessors with Environment. Required observable cases include preprocess extension rewrites delimiters; custom extension tag renders.
- The extracted feature must support this observable behavior: iterate extensions in priority order. Required observable cases include extension ordering by priority.
- The extracted feature must support this observable behavior: render templates using bundled loopcontrols and do extensions. Required observable cases include loopcontrols extension breaks loop; do extension executes side effect; preprocess extension rewrites delimiters; custom extension tag renders.
- The package exposes the required task API paths `featurelifted.Environment`, `featurelifted.Environment.from_string`, `featurelifted.Environment.iter_extensions`, `featurelifted.Extension`, `featurelifted.nodes`, `featurelifted.nodes.CallBlock`, `featurelifted.ext`, `featurelifted.ext.do`, `featurelifted.ext.loopcontrols` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `jinja2, jinja`.
- Do not implement i18n/gettext extension and babel integration.
- Do not implement async rendering and bytecode cache.
- Do not implement loaders and extends/include inheritance graph.
- Do not implement CLI, original tests, docs, packaging metadata.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: load extensions by import path string or Extension subclass. Required observable cases include preprocess extension rewrites delimiters.
- **B002** — The extracted feature must support this observable behavior: register extension tags and preprocessors with Environment. Required observable cases include preprocess extension rewrites delimiters; custom extension tag renders.
- **B003** — The extracted feature must support this observable behavior: iterate extensions in priority order. Required observable cases include extension ordering by priority.
- **B004** — The extracted feature must support this observable behavior: render templates using bundled loopcontrols and do extensions. Required observable cases include loopcontrols extension breaks loop; do extension executes side effect; preprocess extension rewrites delimiters; custom extension tag renders.
- **B005** — The package exposes the required task API paths `featurelifted.Environment`, `featurelifted.Environment.from_string`, `featurelifted.Environment.iter_extensions`, `featurelifted.Extension`, `featurelifted.nodes`, `featurelifted.nodes.CallBlock`, `featurelifted.ext`, `featurelifted.ext.do`, `featurelifted.ext.loopcontrols` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: jinja2, jinja.
<!-- featureliftbench:behavior-clauses:end -->
