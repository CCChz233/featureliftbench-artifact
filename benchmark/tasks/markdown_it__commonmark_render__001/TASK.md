# FeatureLift Task: CommonMark block/inline parsing and HTML rendering

Extract a task-scoped subset of `markdown_it` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    MarkdownIt,
)
```

## Required API Details

- `MarkdownIt(config: 'str | Mapping' = 'commonmark', options_update: 'Mapping | None' = None, *, renderer_cls: 'Callable[[MarkdownIt], RendererProtocol]' = <class 'RendererHTML'>)` class constructor
  - `MarkdownIt.render(self, src: 'str', env: 'MutableMapping | None' = None) -> 'Any'`
  - `MarkdownIt.disable(self, names: 'str | Iterable[str]', ignoreInvalid: 'bool' = False) -> 'MarkdownIt'`
  - `MarkdownIt.enable(self, names: 'str | Iterable[str]', ignoreInvalid: 'bool' = False) -> 'MarkdownIt'`
  - `MarkdownIt.parse(self, src: 'str', env: 'MutableMapping | None' = None) -> 'list[Token]'`

## Required Behavior

- The extracted feature must support this observable behavior: render headings, paragraphs, emphasis, lists, blockquotes, links, images, code spans, and fenced code blocks. Required observable cases include nested blocks code escaping and images; strikethrough and reference links.
- The extracted feature must support this observable behavior: escape raw text correctly in rendered HTML. Required observable cases include commonmark basic html rendering; strikethrough and reference links.
- The extracted feature must support this observable behavior: parse Markdown into Token objects with nesting, tags, attrs, content, and markup. Required observable cases include parse returns useful tokens; strikethrough and reference links.
- The extracted feature must support this observable behavior: support the commonmark preset and enable/disable rules. Required observable cases include fence rule disable and link attributes.
- The package exposes the required task API paths `featurelifted.MarkdownIt`, `featurelifted.MarkdownIt.render`, `featurelifted.MarkdownIt.disable`, `featurelifted.MarkdownIt.enable`, `featurelifted.MarkdownIt.parse` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `markdown_it`.
- Do not implement CLI entrypoints.
- Do not implement plugin ecosystem beyond core parser rules.
- Do not implement documentation and benchmark fixtures.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: render headings, paragraphs, emphasis, lists, blockquotes, links, images, code spans, and fenced code blocks. Required observable cases include nested blocks code escaping and images; strikethrough and reference links.
- **B002** — The extracted feature must support this observable behavior: escape raw text correctly in rendered HTML. Required observable cases include commonmark basic html rendering; strikethrough and reference links.
- **B003** — The extracted feature must support this observable behavior: parse Markdown into Token objects with nesting, tags, attrs, content, and markup. Required observable cases include parse returns useful tokens; strikethrough and reference links.
- **B004** — The extracted feature must support this observable behavior: support the commonmark preset and enable/disable rules. Required observable cases include fence rule disable and link attributes.
- **B005** — The package exposes the required task API paths `featurelifted.MarkdownIt`, `featurelifted.MarkdownIt.render`, `featurelifted.MarkdownIt.disable`, `featurelifted.MarkdownIt.enable`, `featurelifted.MarkdownIt.parse` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: markdown_it.
<!-- featureliftbench:behavior-clauses:end -->
