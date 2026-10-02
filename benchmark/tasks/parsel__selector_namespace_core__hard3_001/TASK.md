# FeatureLift Task: Selector namespaces

Extract a task-scoped subset of `parsel` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    extract_text,
    FakeElement,
    Selector,
    SelectorSyntaxError,
)
```

## Required API Details

- `Selector(root: 'FakeElement') -> 'None'` class constructor
  - `Selector.css(self, query: 'str') -> "'Selector'"`
  - `Selector.xpath(self, query: 'str') -> "'Selector'"`
  - `Selector.register_namespace(prefix: 'str', uri: 'str') -> 'None'`
  - `Selector.remove_namespace(prefix: 'str') -> 'None'`
  - `Selector.get(self, default: 'str | None' = None) -> 'str | None'`
  - `Selector.getall(self) -> 'list[str]'`
- `FakeElement(tag: 'str', text: 'str' = '', tail: 'str' = '', attrib: 'dict[str, str]' = <factory>, children: "list['FakeElement']" = <factory>) -> None` class constructor
- `extract_text(nodes: 'list[FakeElement]', default: 'str' = '') -> 'str'`
- `SelectorSyntaxError` must be importable and raisable

## Required Behavior

- `Selector.css` and `Selector.xpath` select nodes from a lightweight element tree.
- `Selector.register_namespace` enables prefixed XPath tag matching.
- `extract_text` joins nested text with sensible defaults.
- The package exposes the required task API paths `featurelifted.Selector`, `featurelifted.Selector.css`, `featurelifted.Selector.xpath`, `featurelifted.Selector.register_namespace`, `featurelifted.Selector.remove_namespace`, `featurelifted.Selector.get`, `featurelifted.Selector.getall`, `featurelifted.FakeElement`, `featurelifted.extract_text`, `featurelifted.SelectorSyntaxError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `parsel`.
- Forbidden path access: `repo/, parsel/`.
- Do not implement network access.
- Do not implement lxml/cssselect dependencies.
- Do not implement full scrapy stack.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `Selector.css` and `Selector.xpath` select nodes from a lightweight element tree.
- **B002** — `Selector.register_namespace` enables prefixed XPath tag matching.
- **B003** — `extract_text` joins nested text with sensible defaults.
- **B004** — The package exposes the required task API paths `featurelifted.Selector`, `featurelifted.Selector.css`, `featurelifted.Selector.xpath`, `featurelifted.Selector.register_namespace`, `featurelifted.Selector.remove_namespace`, `featurelifted.Selector.get`, `featurelifted.Selector.getall`, `featurelifted.FakeElement`, `featurelifted.extract_text`, `featurelifted.SelectorSyntaxError` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: parsel.
<!-- featureliftbench:behavior-clauses:end -->
