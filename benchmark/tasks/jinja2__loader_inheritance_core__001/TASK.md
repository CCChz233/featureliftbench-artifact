# FeatureLift Task: Jinja2 loader and inheritance core

Extract a task-scoped subset of `jinja2` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    DictLoader,
    Environment,
    exceptions,
    loaders,
)
```

## Required API Details

- `Environment(block_start_string: str = '{%', block_end_string: str = '%}', variable_start_string: str = '{{', variable_end_string: str = '}}', comment_start_string: str = '{#', comment_end_string: str = '#}', line_statement_prefix: Optional[str] = None, line_comment_prefix: Optional[str] = None, trim_blocks: bool = False, lstrip_blocks: bool = False, newline_sequence: "te.Literal['\\n', '\\r\\n', '\\r']" = '\n', keep_trailing_newline: bool = False, extensions: Sequence[Union[str, Type[ForwardRef('Extension')]]] = (), optimized: bool = True, undefined: Type[Undefined] = <class 'Undefined'>, finalize: Optional[Callable[..., Any]] = None, autoescape: Union[bool, Callable[[Optional[str]], bool]] = False, loader: Optional[ForwardRef('BaseLoader')] = None, cache_size: int = 400, auto_reload: bool = True, bytecode_cache: Optional[ForwardRef('BytecodeCache')] = None, enable_async: bool = False)` class constructor
  - `Environment.get_template(self, name: Union[str, ForwardRef('Template')], parent: Optional[str] = None, globals: Optional[MutableMapping[str, Any]] = None) -> 'Template'`
- `DictLoader(mapping: Mapping[str, str]) -> None` class constructor
- `exceptions` module must be importable
  - `exceptions.TemplateNotFound` must be importable and raisable
- `loaders` module must be importable
  - `loaders.BaseLoader()` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: load templates via DictLoader and BaseLoader subclasses. Required observable cases include loader module required for missing template.
- The extracted feature must support this observable behavior: resolve extends chains and block overrides. Required observable cases include extends overrides block; multi level inheritance.
- The extracted feature must support this observable behavior: render nested block inheritance across multiple templates. Required observable cases include multi level inheritance; base loader subclass get source.
- The extracted feature must support this observable behavior: support trim_blocks for layout templates. Required observable cases include multi level inheritance.
- The package exposes the required task API paths `featurelifted.Environment`, `featurelifted.Environment.get_template`, `featurelifted.DictLoader`, `featurelifted.exceptions`, `featurelifted.exceptions.TemplateNotFound`, `featurelifted.loaders`, `featurelifted.loaders.BaseLoader` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `jinja2, jinja`.
- Do not implement PackageLoader zip/import paths beyond DictLoader.
- Do not implement async rendering, extensions, bytecode cache.
- Do not implement CLI, original tests, docs, packaging metadata.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: load templates via DictLoader and BaseLoader subclasses. Required observable cases include loader module required for missing template.
- **B002** — The extracted feature must support this observable behavior: resolve extends chains and block overrides. Required observable cases include extends overrides block; multi level inheritance.
- **B003** — The extracted feature must support this observable behavior: render nested block inheritance across multiple templates. Required observable cases include multi level inheritance; base loader subclass get source.
- **B004** — The extracted feature must support this observable behavior: support trim_blocks for layout templates. Required observable cases include multi level inheritance.
- **B005** — The package exposes the required task API paths `featurelifted.Environment`, `featurelifted.Environment.get_template`, `featurelifted.DictLoader`, `featurelifted.exceptions`, `featurelifted.exceptions.TemplateNotFound`, `featurelifted.loaders`, `featurelifted.loaders.BaseLoader` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: jinja2, jinja.
<!-- featureliftbench:behavior-clauses:end -->
