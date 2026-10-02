# FeatureLift Task: Jinja2 compile and render core

Extract a task-scoped subset of `jinja2` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    compiler,
    Environment,
    runtime,
)
```

## Required API Details

- `Environment(block_start_string: str = '{%', block_end_string: str = '%}', variable_start_string: str = '{{', variable_end_string: str = '}}', comment_start_string: str = '{#', comment_end_string: str = '#}', line_statement_prefix: Optional[str] = None, line_comment_prefix: Optional[str] = None, trim_blocks: bool = False, lstrip_blocks: bool = False, newline_sequence: "te.Literal['\\n', '\\r\\n', '\\r']" = '\n', keep_trailing_newline: bool = False, extensions: Sequence[Union[str, Type[ForwardRef('Extension')]]] = (), optimized: bool = True, undefined: Type[Undefined] = <class 'Undefined'>, finalize: Optional[Callable[..., Any]] = None, autoescape: Union[bool, Callable[[Optional[str]], bool]] = False, loader: Optional[ForwardRef('BaseLoader')] = None, cache_size: int = 400, auto_reload: bool = True, bytecode_cache: Optional[ForwardRef('BytecodeCache')] = None, enable_async: bool = False)` class constructor
  - `Environment.from_string(self, source: Union[str, Template], globals: Optional[MutableMapping[str, Any]] = None, template_class: Optional[Type[ForwardRef('Template')]] = None) -> 'Template'`
  - `Environment.parse(self, source: str, name: Optional[str] = None, filename: Optional[str] = None) -> Template`
- `compiler` module must be importable
  - `compiler.generate(node: Template, environment: 'Environment', name: Optional[str], filename: Optional[str], stream: Optional[TextIO] = None, defer_init: bool = False, optimized: bool = True) -> Optional[str]`
- `runtime` module must be importable
  - `runtime.Context(environment: 'Environment', parent: Dict[str, Any], name: Optional[str], blocks: Dict[str, Callable[[ForwardRef('Context')], Iterator[str]]], globals: Optional[MutableMapping[str, Any]] = None)` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: compile template source to executable code. Required observable cases include runtime context exported vars.
- The extracted feature must support this observable behavior: render templates with context variables. Required observable cases include render simple interpolation; render if for blocks; macro render and caller; runtime context exported vars.
- The extracted feature must support this observable behavior: support if/for/set/macro blocks and expressions. Required observable cases include render if for blocks; macro render and caller; compiler module required for set block.
- The extracted feature must support this observable behavior: preserve undefined variable behavior with default Undefined. Required observable cases include runtime context exported vars.
- The package exposes the required task API paths `featurelifted.Environment`, `featurelifted.Environment.from_string`, `featurelifted.Environment.parse`, `featurelifted.compiler`, `featurelifted.compiler.generate`, `featurelifted.runtime`, `featurelifted.runtime.Context` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `jinja2, jinja`.
- Do not implement loaders and extends/include inheritance graph.
- Do not implement async rendering.
- Do not implement extensions, bytecode cache, i18n.
- Do not implement CLI, original tests, docs, packaging metadata.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: compile template source to executable code. Required observable cases include runtime context exported vars.
- **B002** — The extracted feature must support this observable behavior: render templates with context variables. Required observable cases include render simple interpolation; render if for blocks; macro render and caller; runtime context exported vars.
- **B003** — The extracted feature must support this observable behavior: support if/for/set/macro blocks and expressions. Required observable cases include render if for blocks; macro render and caller; compiler module required for set block.
- **B004** — The extracted feature must support this observable behavior: preserve undefined variable behavior with default Undefined. Required observable cases include runtime context exported vars.
- **B005** — The package exposes the required task API paths `featurelifted.Environment`, `featurelifted.Environment.from_string`, `featurelifted.Environment.parse`, `featurelifted.compiler`, `featurelifted.compiler.generate`, `featurelifted.runtime`, `featurelifted.runtime.Context` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: jinja2, jinja.
<!-- featureliftbench:behavior-clauses:end -->
