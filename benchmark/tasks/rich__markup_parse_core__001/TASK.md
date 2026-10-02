# FeatureLift Task: Console markup parsing

Extract a task-scoped subset of `rich` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    errors,
    markup,
    text,
)
```

## Required API Details

- `errors` module must be importable
  - `errors.MarkupError` must be importable and raisable
- `markup` module must be importable
  - `markup.escape(markup: str, _escape: Callable[[Callable[[Match[str]], str], str], str] = <built-in method sub of re.Pattern object>) -> str`
  - `markup.render(markup: str, style: Union[str, Style] = '', emoji: bool = True, emoji_variant: Optional[Literal['emoji', 'text']] = None) -> Text`
- `text` module must be importable
  - `text.Text(text: str = '', style: Union[str, Style] = '', *, justify: Optional[ForwardRef('JustifyMethod')] = None, overflow: Optional[ForwardRef('OverflowMethod')] = None, no_wrap: Optional[bool] = None, end: str = '\n', tab_size: Optional[int] = None, spans: Optional[List[Span]] = None) -> None` class constructor
    - `text.Text.from_markup(text: str, *, style: Union[str, Style] = '', emoji: bool = True, emoji_variant: Optional[Literal['emoji', 'text']] = None, justify: Optional[ForwardRef('JustifyMethod')] = None, overflow: Optional[ForwardRef('OverflowMethod')] = None, end: str = '\n') -> 'Text'`
    - `text.Text.markup` attribute must exist on instances
    - `text.Text.plain` attribute must exist on instances
    - `text.Text.spans` attribute must exist on instances

## Required Behavior

- The extracted feature must support this observable behavior: render markup tags into Text with style spans. Required observable cases include render escape and from markup; nested styles and implicit close; markup errors and escaped brackets; meta link handler and repr.
- The extracted feature must support this observable behavior: escape square brackets for literal markup. Required observable cases include render escape and from markup; markup errors and escaped brackets.
- The extracted feature must support this observable behavior: support nested/open/close tags and link metadata. Required observable cases include nested styles and implicit close; meta link handler and repr.
- The extracted feature must support this observable behavior: raise MarkupError on mismatched closing tags. Required observable cases include nested styles and implicit close.
- The package exposes the required task API paths `featurelifted.errors`, `featurelifted.errors.MarkupError`, `featurelifted.markup`, `featurelifted.markup.escape`, `featurelifted.markup.render`, `featurelifted.text`, `featurelifted.text.Text`, `featurelifted.text.Text.from_markup`, `featurelifted.text.Text.markup`, `featurelifted.text.Text.plain`, `featurelifted.text.Text.spans` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `rich`.
- Do not implement full Console rendering pipeline and terminal detection.
- Do not implement progress bars, tables, and layout renderables.
- Do not implement syntax highlighting and live displays.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: render markup tags into Text with style spans. Required observable cases include render escape and from markup; nested styles and implicit close; markup errors and escaped brackets; meta link handler and repr.
- **B002** — The extracted feature must support this observable behavior: escape square brackets for literal markup. Required observable cases include render escape and from markup; markup errors and escaped brackets.
- **B003** — The extracted feature must support this observable behavior: support nested/open/close tags and link metadata. Required observable cases include nested styles and implicit close; meta link handler and repr.
- **B004** — The extracted feature must support this observable behavior: raise MarkupError on mismatched closing tags. Required observable cases include nested styles and implicit close.
- **B005** — The package exposes the required task API paths `featurelifted.errors`, `featurelifted.errors.MarkupError`, `featurelifted.markup`, `featurelifted.markup.escape`, `featurelifted.markup.render`, `featurelifted.text`, `featurelifted.text.Text`, `featurelifted.text.Text.from_markup`, `featurelifted.text.Text.markup`, `featurelifted.text.Text.plain`, `featurelifted.text.Text.spans` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: rich.
<!-- featureliftbench:behavior-clauses:end -->
