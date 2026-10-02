# FeatureLift Task: Item loader processor registry

Extract a task-scoped subset of `scrapy` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Compose,
    Field,
    Item,
    ItemLoader,
    TakeFirst,
)
```

## Required API Details

- `Item(*args, **kwargs)` class constructor
- `Field(*args, **kwargs)` class constructor
- `ItemLoader(item: 'type[Item] | Item | None' = None, parent: "'ItemLoader | None'" = None, **context)` class constructor
  - `ItemLoader.__init__(self, item: 'type[Item] | Item | None' = None, parent: "'ItemLoader | None'" = None, **context)`
  - `ItemLoader.add_value(self, field_name: 'str', value: 'Any') -> 'None'`
  - `ItemLoader.load_item(self) -> 'Item'`
  - `ItemLoader.default_output_processor` attribute must exist on instances
- `Compose(*processors: 'Callable') -> 'Callable'`
- `TakeFirst()`

## Required Behavior

- When an Item declares Field metadata with input or output processors, those processors are attached to the field definition.
- When ItemLoader.add_value runs input processors and load_item runs output processors, the resulting item values reflect the processor pipeline.
- When a nested ItemLoader is created with parent=..., it inherits the parent default processor types.
- The package exposes the required task API paths `featurelifted.Item`, `featurelifted.Field`, `featurelifted.ItemLoader`, `featurelifted.ItemLoader.__init__`, `featurelifted.ItemLoader.add_value`, `featurelifted.ItemLoader.load_item`, `featurelifted.ItemLoader.default_output_processor`, `featurelifted.Compose`, `featurelifted.TakeFirst` with the kinds and callable signatures listed in this contract.
- When add_value is called for an undefined field name, ItemLoader raises KeyError.

## Constraints

- Forbidden imports: `scrapy`.
- Forbidden path access: `repo/, scrapy/`.
- Do not implement network access.
- Do not implement selector/response extraction.
- Do not implement downloader/crawler code.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When an Item declares Field metadata with input or output processors, those processors are attached to the field definition.
- **B002** — When ItemLoader.add_value runs input processors and load_item runs output processors, the resulting item values reflect the processor pipeline.
- **B003** — When a nested ItemLoader is created with parent=..., it inherits the parent default processor types.
- **B004** — The package exposes the required task API paths `featurelifted.Item`, `featurelifted.Field`, `featurelifted.ItemLoader`, `featurelifted.ItemLoader.__init__`, `featurelifted.ItemLoader.add_value`, `featurelifted.ItemLoader.load_item`, `featurelifted.ItemLoader.default_output_processor`, `featurelifted.Compose`, `featurelifted.TakeFirst` with the kinds and callable signatures listed in this contract.
- **B006** — When add_value is called for an undefined field name, ItemLoader raises KeyError.
- **B005** — The submitted package does not import forbidden upstream packages: scrapy.
<!-- featureliftbench:behavior-clauses:end -->
