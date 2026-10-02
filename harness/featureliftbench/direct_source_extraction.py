"""Entrypoint-guided mechanical extraction, without executing upstream code.

Input is a pinned full source tree and public_spec only. This module never reads
benchmark tests, reference solutions, evaluator results, or model outputs.
"""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
import tokenize
from collections import defaultdict, deque
from pathlib import Path

VERSION = 'dse-static-closure-v1.2-reviewed'
EXCLUDE = {'tests', 'test', 'testing', 'docs', 'doc', 'examples', 'example',
           '.git', '__pycache__', '.venv', 'build', 'dist'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_python(path: Path) -> str:
    with tokenize.open(path) as handle:
        return handle.read()


def bindings(nodes):
    for node in nodes:
        yield node
        if isinstance(node, (ast.If, ast.Try)):
            yield from bindings(node.body)
            yield from bindings(node.orelse)
            if isinstance(node, ast.Try):
                yield from bindings(node.finalbody)
                for handler in node.handlers:
                    yield from bindings(handler.body)


class SourceIndex:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.modules: dict[str, Path] = {}
        self.ambiguous: dict[str, list[str]] = {}
        self.cache = {}
        paths = sorted(p for p in root.rglob('*.py') if p.is_file()
                       and p.resolve().is_relative_to(self.root)
                       and not any(x in EXCLUDE or x.startswith('.') for x in p.relative_to(root).parts))
        bases = {root}
        bases.update(p.parent for p in paths if p.parent.name in {'src', 'lib'})
        bases.update(parent for p in paths for parent in p.parents
                     if parent != root and parent.is_relative_to(root) and parent.name in {'src', 'lib'})
        candidates = defaultdict(set)
        for base in sorted(bases):
            for path in paths:
                if not path.is_relative_to(base):
                    continue
                parts = list(path.relative_to(base).with_suffix('').parts)
                if parts[-1] == '__init__':
                    parts.pop()
                if parts and all(x.isidentifier() for x in parts):
                    candidates['.'.join(parts)].add(path)
        # A literal full_package_name in a root package is a source-declared layout.
        init = root / '__init__.py'
        if init.is_file():
            try:
                tree = ast.parse(read_python(init))
                prefixes = {k.value.value for n in ast.walk(tree) if isinstance(n, ast.Call)
                            for k in n.keywords if k.arg == 'full_package_name'
                            and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str)}
                for prefix in prefixes:
                    if not all(x.isidentifier() for x in prefix.split('.')):
                        continue
                    for path in paths:
                        parts = list(path.relative_to(root).with_suffix('').parts)
                        if parts[-1] == '__init__':
                            parts.pop()
                        if all(x.isidentifier() for x in parts):
                            candidates['.'.join([prefix, *parts])].add(path)
            except (SyntaxError, UnicodeError):
                pass
        for name, matches in candidates.items():
            if len(matches) == 1:
                self.modules[name] = next(iter(matches))
            else:
                self.ambiguous[name] = sorted(str(p.relative_to(root)) for p in matches)
        self.namespaces = {'.'.join(m.split('.')[:i]) for m in self.modules
                           for i in range(1, len(m.split('.')))}

    def tree(self, module):
        path = self.modules.get(module)
        if path is None:
            return None
        if path not in self.cache:
            try:
                self.cache[path] = ast.parse(read_python(path))
            except (SyntaxError, UnicodeError):
                self.cache[path] = None
        return self.cache[path]

    def has_module(self, name):
        return name in self.modules or name in self.namespaces

    def imported_base(self, module, node):
        if not node.level:
            return node.module or ''
        path = self.modules[module]
        parts = module.split('.') if path.name == '__init__.py' else module.split('.')[:-1]
        if node.level > len(parts):
            return ''
        parts = parts[:len(parts) - node.level + 1]
        return '.'.join(parts + ([node.module] if node.module else []))

    def resolve(self, target, seen=()):
        if target in seen or len(seen) > 16:
            return None
        # Some public entrypoints retain a source-layout prefix, not an import name.
        target = target.removeprefix('src.').removeprefix('lib.')
        parts = target.split('.')
        # Public locations sometimes spell out a package's __init__.py file.
        for i, part in enumerate(parts):
            prefix = '.'.join(parts[:i])
            if (part == '__init__' and prefix in self.modules
                    and self.modules[prefix].name == '__init__.py'):
                return self.resolve('.'.join(parts[:i] + parts[i + 1:]), (*seen, target))
        for cut in range(len(parts), 0, -1):
            module = '.'.join(parts[:cut])
            if module not in self.modules:
                continue
            attrs = parts[cut:]
            if not attrs:
                return module, ()
            tree = self.tree(module)
            if tree is None:
                return None
            name = attrs[0]
            for node in bindings(tree.body):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
                    if len(attrs) > 1:
                        if not isinstance(node, ast.ClassDef):
                            continue
                        return self.class_member(module, node, attrs[1:], (*seen, target))
                    return module, tuple(attrs)
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    if len(attrs) == 1 and any(isinstance(t, ast.Name) and t.id == name for t in targets):
                        return module, tuple(attrs)
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if (alias.asname or alias.name) == name:
                            imported = self.imported_base(module, node)
                            resolved = self.resolve('.'.join(filter(None, [imported, alias.name, *attrs[1:]])), (*seen, target))
                            if resolved:
                                return resolved
                        elif alias.name == '*' and not name.startswith('_'):
                            imported = self.imported_base(module, node)
                            imported_tree = self.tree(imported)
                            if imported_tree is None:
                                continue
                            export_list = None
                            unknown_export_list = False
                            for statement in bindings(imported_tree.body):
                                if isinstance(statement, ast.Assign) and any(
                                    isinstance(t, ast.Name) and t.id == '__all__' for t in statement.targets
                                ):
                                    try:
                                        export_list = ast.literal_eval(statement.value)
                                    except (ValueError, TypeError):
                                        unknown_export_list = True
                            if unknown_export_list or (export_list is not None and name not in export_list):
                                continue
                            resolved = self.resolve('.'.join([imported, *attrs]), (*seen, target))
                            if resolved:
                                return resolved
            return None
        return None

    def class_member(self, module, cls, attrs, seen):
        # Resolve real class scope, not same-named locals inside a method.
        for node in bindings(cls.body):
            if getattr(node, 'name', None) == attrs[0]:
                if len(attrs) == 1:
                    return module, (cls.name, attrs[0])
                # Nested classes / dynamic descriptors are outside this rule.
                return None
        # Only a single statically named base is supported; do not guess MRO.
        if len(cls.bases) == 1 and isinstance(cls.bases[0], ast.Name):
            return self.resolve('.'.join([module, cls.bases[0].id, *attrs]), seen)
        return None

    def closure(self, seeds):
        selected, queue, unresolved = set(), deque(sorted(seeds)), set()
        while queue:
            module = queue.popleft()
            if module in selected or not self.has_module(module):
                continue
            selected.add(module)
            queue.extend('.'.join(module.split('.')[:i]) for i in range(1, len(module.split('.'))))
            tree = self.tree(module)
            if tree is None:
                continue
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    base = self.imported_base(module, node)
                    names = [base] + ['.'.join(filter(None, [base, a.name])) for a in node.names if a.name != '*']
                for name in names:
                    if self.has_module(name):
                        queue.append(name)
                    elif name:
                        unresolved.add(name)
        return selected, sorted(unresolved)


def relocated(module, roots):
    top, *rest = module.split('.')
    return '.'.join(['featurelifted', roots[top], *rest])


def rewrite_imports(text, roots):
    """Replace import statement spans only; retain all other source bytes as text.

    AST columns count UTF-8 bytes, hence edits operate on UTF-8 data. Unaliased
    dotted imports require a second binding to preserve Python's root binding.
    """
    tree = ast.parse(text)
    lines = text.encode('utf-8').splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits = []
    for node in ast.walk(tree):
        replacement = None
        if isinstance(node, ast.Import):
            statements = []
            changed = False
            for alias in node.names:
                top = alias.name.split('.')[0]
                if top not in roots:
                    statements.append(ast.unparse(ast.Import(names=[alias])))
                    continue
                changed = True
                target = relocated(alias.name, roots)
                if alias.asname:
                    statements.append(f'import {target} as {alias.asname}')
                elif '.' in alias.name:
                    statements.extend([f'import {target}', f'import {relocated(top, roots)} as {top}'])
                else:
                    statements.append(f'import {target} as {top}')
            if changed:
                replacement = '; '.join(statements)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module and node.module.split('.')[0] in roots:
            replacement = ast.unparse(ast.ImportFrom(module=relocated(node.module, roots), names=node.names, level=0))
        if replacement is not None:
            start = offsets[node.lineno - 1] + node.col_offset
            end = offsets[node.end_lineno - 1] + node.end_col_offset
            edits.append((start, end, replacement.encode()))
    result = text.encode('utf-8')
    for start, end, replacement in sorted(edits, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result.decode('utf-8'), len(edits)


def extract(source: Path, public_spec: dict, output: Path, *, reviewed_aliases=None) -> dict:
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite submission: {output}')
    index = SourceIndex(source)
    entries = public_spec.get('source_entrypoints', [])
    mapped = {e: index.resolve(e) for e in entries}
    seeds = {value[0] for value in mapped.values() if value}
    selected, external = index.closure(seeds)
    api_rows = public_spec.get('required_api', [])
    # Collect each destination top-level API and whether it denotes a module.
    tops = {}
    for row in api_rows:
        path = row.get('path', '').split('.')
        if len(path) >= 2 and path[0] == 'featurelifted':
            tops.setdefault(path[1], row.get('kind') if len(path) == 2 else None)
    exports, unresolved = {}, {}
    for name, kind in sorted(tops.items()):
        tiers = []
        tiers.append({v for e, v in mapped.items() if v and e.split('.')[-1] == name and len(v[1]) <= 1})
        top_roots = {m.split('.')[0] for m in selected}
        tiers.append({v for root in top_roots if (v := index.resolve(root + '.' + name)) and len(v[1]) <= 1})
        if kind == 'module':
            tiers.append({(m, ()) for m in selected if m.split('.')[-1] == name})
        tiers.append({v for m in selected if (v := index.resolve(m + '.' + name)) and len(v[1]) == 1})
        found = next((tier for tier in tiers if tier), set())
        if len(found) == 1:
            exports[name] = next(iter(found))
        else:
            unresolved[name] = 'ambiguous' if found else 'no_same_name_static_binding'
    # A frozen, public-source-reviewed map may supply name-only re-exports.
    # It cannot replace an existing binding or synthesize any callable/body.
    applied_aliases = {}
    for name, target in sorted((reviewed_aliases or {}).items()):
        if name not in tops or name in exports:
            raise ValueError(f'Reviewed alias must name an unresolved required API: {name}')
        value = index.resolve(target)
        if value is None or len(value[1]) != 1:
            raise ValueError(f'Reviewed alias must resolve to a top-level source binding: {target}')
        exports[name] = value
        unresolved.pop(name)
        applied_aliases[name] = target
    selected, external = index.closure(selected | {v[0] for v in exports.values()})
    roots = {name: f'_dse_p{i}' for i, name in enumerate(sorted({m.split('.')[0] for m in selected}))}
    output.mkdir(parents=True)
    pkg = output / 'featurelifted'
    pkg.mkdir()
    copied, diagnostics = [], []
    for module in sorted(selected):
        original = index.modules.get(module)
        new = Path(*relocated(module, roots).split('.'))
        is_package = original is None or original.name == '__init__.py'
        dest = output / new / '__init__.py' if is_package else output / new.with_suffix('.py')
        dest.parent.mkdir(parents=True, exist_ok=True)
        if original is None:
            dest.write_text('# Mechanical namespace package.\n')
            continue
        text = read_python(original)
        try:
            changed, count = rewrite_imports(text, roots)
        except SyntaxError as exc:
            diagnostics.append({'module': module, 'kind': 'source_syntax_unsupported', 'line': exc.lineno})
            changed, count = text, 0
        # Preserve the original declared encoding when possible.
        with original.open('rb') as handle:
            encoding, _ = tokenize.detect_encoding(handle.readline)
        dest.write_bytes(changed.encode(encoding))
        copied.append({'source': str(original.relative_to(source)), 'destination': str(dest.relative_to(output)),
                       'source_sha256': sha(original), 'output_sha256': sha(dest), 'import_edits': count})
        tree = index.tree(module)
        if tree:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and ((isinstance(node.func, ast.Name) and node.func.id in {'__import__', 'import_module'})
                    or (isinstance(node.func, ast.Attribute) and node.func.attr in {'import_module', 'get_data', 'resource_filename', 'files', 'version'})):
                    diagnostics.append({'module': module, 'kind': 'dynamic_import_or_resource_call_unmodified', 'line': node.lineno})
    resources = []
    # Non-code files beneath selected packages; no test/docs trees, no root source checkout.
    for module in sorted(selected):
        original = index.modules.get(module)
        if original is None or original.name != '__init__.py':
            continue
        base = original.parent
        for resource in sorted(base.rglob('*')):
            rel = resource.relative_to(base)
            if (not resource.is_file() or resource.suffix in {'.py', '.pyc', '.pyo'}
                or any(p in EXCLUDE or p.startswith('.') for p in rel.parts)
                or not resource.resolve().is_relative_to(source.resolve())):
                continue
            dest = output.joinpath(*relocated(module, roots).split('.')) / rel
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resource, dest)
            resources.append({'source': str(resource.relative_to(source)), 'destination': str(dest.relative_to(output)), 'sha256': sha(dest)})
    init = ['"""Mechanically exported source API; no behavioral repair."""']
    for name, (module, attrs) in sorted(exports.items()):
        if attrs:
            init.append(f'from {relocated(module, roots)} import {attrs[0]} as {name}')
        else:
            init.append(f'import {relocated(module, roots)} as {name}')
    (pkg / '__init__.py').write_text('\n'.join(init) + '\n')
    (output / 'pyproject.toml').write_text('''[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
[project]
name = "featurelifted"
version = "0.0.0"
[tool.setuptools.packages.find]
where = ["."]
include = ["featurelifted*"]
[tool.setuptools.package-data]
"*" = ["**/*"]
''')
    return {'algorithm': VERSION, 'entrypoint_mappings': mapped,
            'unresolved_entrypoints': [e for e, v in mapped.items() if not v],
            'export_mappings': exports, 'unresolved_api': unresolved,
            'reviewed_aliases_applied': applied_aliases,
            'namespace_mapping': roots, 'selected_modules': sorted(selected),
            'external_or_unresolved_import_names': external, 'copied_python': copied,
            'copied_resources': resources, 'diagnostics': diagnostics,
            'ambiguous_module_layouts': index.ambiguous,
            'generation_status': 'no_entrypoint_resolved' if not seeds else 'generated',
            'functional_status': 'not_evaluated'}
