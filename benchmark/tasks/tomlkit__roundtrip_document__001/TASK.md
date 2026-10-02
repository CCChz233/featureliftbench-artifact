# FeatureLift Task: TOML document parse and round-trip editing

Extract a task-scoped subset of `tomlkit` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    aot,
    array,
    document,
    dumps,
    exceptions,
    inline_table,
    item,
    loads,
    parse,
    string,
    table,
)
```

## Required API Details

- `parse(string: 'str | bytes') -> 'TOMLDocument'`
- `loads(string: 'str | bytes') -> 'TOMLDocument'`
- `dumps(data: 'Mapping[str, Any]', sort_keys: 'bool' = False) -> 'str'`
- `document() -> 'TOMLDocument'`
- `table(is_super_table: 'bool | None' = None) -> 'Table'`
- `inline_table() -> 'InlineTable'`
- `array(raw: 'str' = '[]') -> 'Array'`
- `aot() -> 'AoT'`
- `string(raw: 'str', *, literal: 'bool' = False, multiline: 'bool' = False, escape: 'bool' = True) -> 'String'`
- `item(value: 'Any', _parent: 'Item | None' = None, _sort_keys: 'bool' = False) -> 'Item'`
- `exceptions` module must be importable
  - `exceptions.InvalidUnicodeValueError` must be importable and raisable
  - `exceptions.ParseError` must be importable and raisable
  - `exceptions.UnexpectedCharError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: parse TOML strings and bytes into mutable TOMLDocument objects. Required observable cases include string constructor and sorted dump preserve expected format.
- The extracted feature must support this observable behavior: preserve comments, blank lines, table order, inline tables, literal strings, multiline strings, and array formatting when dumping parsed documents. Required observable cases include parse document values and roundtrip layout; editing preserves table order and comments; inline table array and parse errors; multiline literal strings and trailing comma arrays roundtrip.
- The extracted feature must support this observable behavior: dump plain mappings, nested mappings, arrays, inline tables, and arrays of tables. Required observable cases include dump plain mappings and build document; arrays of tables and inline tables dump correctly.
- The extracted feature must support this observable behavior: support document/table/inline_table/array/aot/string/item constructors. Required observable cases include inline table array and parse errors; arrays of tables and inline tables dump correctly; string constructor and sorted dump preserve expected format.
- The extracted feature must support this observable behavior: support sorted-key dumping for mappings and parsed documents. Required observable cases include parse document values and roundtrip layout; dump plain mappings and build document; string constructor and sorted dump preserve expected format.
- The extracted feature must support this observable behavior: support datetime, date, time, integers, floats, booleans, arrays, tables, dotted keys, and unicode strings. Required observable cases include dotted keys table redefinition and unicode errors.
- The extracted feature must support this observable behavior: raise stable ParseError subclasses with line and column information for malformed TOML. Required observable cases include string constructor and sorted dump preserve expected format.
- The package exposes the required task API paths `featurelifted.parse`, `featurelifted.loads`, `featurelifted.dumps`, `featurelifted.document`, `featurelifted.table`, `featurelifted.inline_table`, `featurelifted.array`, `featurelifted.aot`, `featurelifted.string`, `featurelifted.item`, `featurelifted.exceptions`, `featurelifted.exceptions.InvalidUnicodeValueError`, and 2 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `tomlkit`.
- Do not implement original project tests.
- Do not implement original documentation.
- Do not implement release tooling and CI configuration.
- Do not implement packaging metadata from the original project.
- Do not implement external toml compliance test fixtures.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse TOML strings and bytes into mutable TOMLDocument objects. Required observable cases include string constructor and sorted dump preserve expected format.
- **B002** — The extracted feature must support this observable behavior: preserve comments, blank lines, table order, inline tables, literal strings, multiline strings, and array formatting when dumping parsed documents. Required observable cases include parse document values and roundtrip layout; editing preserves table order and comments; inline table array and parse errors; multiline literal strings and trailing comma arrays roundtrip.
- **B003** — The extracted feature must support this observable behavior: dump plain mappings, nested mappings, arrays, inline tables, and arrays of tables. Required observable cases include dump plain mappings and build document; arrays of tables and inline tables dump correctly.
- **B004** — The extracted feature must support this observable behavior: support document/table/inline_table/array/aot/string/item constructors. Required observable cases include inline table array and parse errors; arrays of tables and inline tables dump correctly; string constructor and sorted dump preserve expected format.
- **B005** — The extracted feature must support this observable behavior: support sorted-key dumping for mappings and parsed documents. Required observable cases include parse document values and roundtrip layout; dump plain mappings and build document; string constructor and sorted dump preserve expected format.
- **B006** — The extracted feature must support this observable behavior: support datetime, date, time, integers, floats, booleans, arrays, tables, dotted keys, and unicode strings. Required observable cases include dotted keys table redefinition and unicode errors.
- **B007** — The extracted feature must support this observable behavior: raise stable ParseError subclasses with line and column information for malformed TOML. Required observable cases include string constructor and sorted dump preserve expected format.
- **B008** — The package exposes the required task API paths `featurelifted.parse`, `featurelifted.loads`, `featurelifted.dumps`, `featurelifted.document`, `featurelifted.table`, `featurelifted.inline_table`, `featurelifted.array`, `featurelifted.aot`, `featurelifted.string`, `featurelifted.item`, `featurelifted.exceptions`, `featurelifted.exceptions.InvalidUnicodeValueError`, and 2 listed members with the kinds and callable signatures listed in this contract.
- **B009** — the submitted package does not import forbidden upstream packages: tomlkit.
<!-- featureliftbench:behavior-clauses:end -->
