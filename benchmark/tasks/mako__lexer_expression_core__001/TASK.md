# FeatureLift Task: Mako template lexer and expression parse core

Extract a task-scoped subset of `mako` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    CompileException,
    Lexer,
    parsetree,
    PythonCode,
    PythonFragment,
    SyntaxException,
)
```

## Required API Details

- `Lexer(text, filename=None, input_encoding=None, preprocessor=None)` class constructor
  - `Lexer.parse(self)`
- `parsetree` module must be importable
  - `parsetree.ControlLine(keyword, isend, text, **kwargs)` class constructor
  - `parsetree.DefTag(keyword, attributes, **kwargs)` class constructor
  - `parsetree.Expression(text, escapes, **kwargs)` class constructor
  - `parsetree.TemplateNode(filename)` class constructor
  - `parsetree.Text(content, **kwargs)` class constructor
- `PythonCode(code, **exception_kwargs)` class constructor
  - `PythonCode.declared_identifiers` attribute must exist on instances
  - `PythonCode.undeclared_identifiers` attribute must exist on instances
- `PythonFragment(code, **exception_kwargs)` class constructor
  - `PythonFragment.declared_identifiers` attribute must exist on instances
  - `PythonFragment.undeclared_identifiers` attribute must exist on instances
- `SyntaxException` must be importable and raisable
- `CompileException` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: lex template source into parsetree nodes (text, expression, control, tags). Required observable cases include parse text and expression; def tag parses; percent escape in template; unclosed tag raises syntax; expression filter escapes; invalid partial control raises compile.
- The extracted feature must support this observable behavior: parse ${...} expressions and % control lines. Required observable cases include parse text and expression; parse control line; def tag parses; expression filter escapes; elif partial control identifiers; invalid partial control raises compile.
- The extracted feature must support this observable behavior: analyze Python fragments for declared and undeclared identifiers. Required observable cases include python code undeclared; python fragment for loop; elif partial control identifiers.
- The extracted feature must support this observable behavior: report SyntaxException and CompileException with line positions. Required observable cases include unclosed tag raises syntax.
- The package exposes the required task API paths `featurelifted.Lexer`, `featurelifted.Lexer.parse`, `featurelifted.parsetree`, `featurelifted.parsetree.ControlLine`, `featurelifted.parsetree.DefTag`, `featurelifted.parsetree.Expression`, `featurelifted.parsetree.TemplateNode`, `featurelifted.parsetree.Text`, `featurelifted.PythonCode`, `featurelifted.PythonCode.declared_identifiers`, `featurelifted.PythonCode.undeclared_identifiers`, `featurelifted.PythonFragment`, and 4 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `mako`.
- Do not implement template compilation, codegen, and runtime rendering.
- Do not implement TemplateLookup, caching, and filesystem loading.
- Do not implement CLI, extensions, babel/beaker plugins.
- Do not implement original mako import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: lex template source into parsetree nodes (text, expression, control, tags). Required observable cases include parse text and expression; def tag parses; percent escape in template; unclosed tag raises syntax; expression filter escapes; invalid partial control raises compile.
- **B002** — The extracted feature must support this observable behavior: parse ${...} expressions and % control lines. Required observable cases include parse text and expression; parse control line; def tag parses; expression filter escapes; elif partial control identifiers; invalid partial control raises compile.
- **B003** — The extracted feature must support this observable behavior: analyze Python fragments for declared and undeclared identifiers. Required observable cases include python code undeclared; python fragment for loop; elif partial control identifiers.
- **B004** — The extracted feature must support this observable behavior: report SyntaxException and CompileException with line positions. Required observable cases include unclosed tag raises syntax.
- **B005** — The package exposes the required task API paths `featurelifted.Lexer`, `featurelifted.Lexer.parse`, `featurelifted.parsetree`, `featurelifted.parsetree.ControlLine`, `featurelifted.parsetree.DefTag`, `featurelifted.parsetree.Expression`, `featurelifted.parsetree.TemplateNode`, `featurelifted.parsetree.Text`, `featurelifted.PythonCode`, `featurelifted.PythonCode.declared_identifiers`, `featurelifted.PythonCode.undeclared_identifiers`, `featurelifted.PythonFragment`, and 4 listed members with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: mako.
<!-- featureliftbench:behavior-clauses:end -->
