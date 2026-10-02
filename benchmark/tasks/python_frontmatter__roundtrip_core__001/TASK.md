# FeatureLift Task: YAML front matter round-trip

Extract a task-scoped subset of `frontmatter` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    checks,
    dump,
    dumps,
    load,
    loads,
    parse,
    Post,
)
```

## Required API Details

- `Post(content: 'str', handler: 'BaseHandler | None' = None, **metadata: 'object') -> 'None'` class constructor
  - `Post.content` attribute must exist on instances
  - `Post.metadata` attribute must exist on instances
  - `Post.to_dict(self) -> 'dict[str, object]'`
  - `Post.__getitem__(self, name: 'str') -> 'object'`
- `parse(text: 'str', encoding: 'str' = 'utf-8', handler: 'BaseHandler | None' = None, **defaults: 'object') -> 'tuple[dict[str, object], str]'`
- `load(fd: 'str | io.IOBase | pathlib.Path', encoding: 'str' = 'utf-8', handler: 'BaseHandler | None' = None, **defaults: 'object') -> 'Post'`
- `loads(text: 'str', encoding: 'str' = 'utf-8', handler: 'BaseHandler | None' = None, **defaults: 'object') -> 'Post'`
- `dump(post: 'Post', fd: 'str | PathLike[str] | TextIO', encoding: 'str' = 'utf-8', handler: 'BaseHandler | None' = None, **kwargs: 'object') -> 'None'`
- `dumps(post: 'Post', handler: 'BaseHandler | None' = None, **kwargs: 'object') -> 'str'`
- `checks(text: 'str', encoding: 'str' = 'utf-8') -> 'bool'`

## Required Behavior

- The extracted feature must support this observable behavior: parse and loads YAML front matter delimited by --- lines. Required observable cases include loads yaml frontmatter; parse returns metadata and content; empty frontmatter block.
- The extracted feature must support this observable behavior: dump and dumps serialize Post metadata and markdown body. Required observable cases include dumps roundtrip metadata and body; no frontmatter returns empty metadata; unicode metadata roundtrip; custom dump delimiters.
- The extracted feature must support this observable behavior: detect delimiter lines with optional trailing whitespace. Required observable cases include extra space after opening delimiter; checks detects frontmatter.
- The extracted feature must support this observable behavior: normalize CRLF input and merge parse defaults. Required observable cases include parse returns metadata and content; crlf bytes normalize; parse defaults merge.
- The extracted feature must support this observable behavior: Post dict-like metadata access and to_dict export. Required observable cases include no frontmatter returns empty metadata; unicode metadata roundtrip; post to dict.
- The package exposes the required task API paths `featurelifted.Post`, `featurelifted.Post.content`, `featurelifted.Post.metadata`, `featurelifted.Post.to_dict`, `featurelifted.Post.__getitem__`, `featurelifted.parse`, `featurelifted.load`, `featurelifted.loads`, `featurelifted.dump`, `featurelifted.dumps`, `featurelifted.checks` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `frontmatter`.
- Do not implement TOML and JSON handler round-trips.
- Do not implement CLI, Sphinx docs, examples, and upstream test suite.
- Do not implement original frontmatter import at runtime.
- Do not implement pyaml pretty-dump integration.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse and loads YAML front matter delimited by --- lines. Required observable cases include loads yaml frontmatter; parse returns metadata and content; empty frontmatter block.
- **B002** — The extracted feature must support this observable behavior: dump and dumps serialize Post metadata and markdown body. Required observable cases include dumps roundtrip metadata and body; no frontmatter returns empty metadata; unicode metadata roundtrip; custom dump delimiters.
- **B003** — The extracted feature must support this observable behavior: detect delimiter lines with optional trailing whitespace. Required observable cases include extra space after opening delimiter; checks detects frontmatter.
- **B004** — The extracted feature must support this observable behavior: normalize CRLF input and merge parse defaults. Required observable cases include parse returns metadata and content; crlf bytes normalize; parse defaults merge.
- **B005** — The extracted feature must support this observable behavior: Post dict-like metadata access and to_dict export. Required observable cases include no frontmatter returns empty metadata; unicode metadata roundtrip; post to dict.
- **B006** — The package exposes the required task API paths `featurelifted.Post`, `featurelifted.Post.content`, `featurelifted.Post.metadata`, `featurelifted.Post.to_dict`, `featurelifted.Post.__getitem__`, `featurelifted.parse`, `featurelifted.load`, `featurelifted.loads`, `featurelifted.dump`, `featurelifted.dumps`, `featurelifted.checks` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: frontmatter.
<!-- featureliftbench:behavior-clauses:end -->
