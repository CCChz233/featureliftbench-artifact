from pathlib import Path
import json
import subprocess
import sys

from featureliftbench.direct_source_extraction import SourceIndex, extract, rewrite_imports


def put(root, name, content):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def test_relocation_preserves_import_bindings_and_resources(tmp_path):
    source, out = tmp_path / 'source', tmp_path / 'submission'
    put(source, 'src/alpha/__init__.py', 'from .core import answer\n')
    put(source, 'src/alpha/core.py', 'import alpha.dep\nfrom alpha.dep import value as v\ndef answer():\n    return alpha.dep.value + v\n')
    put(source, 'src/alpha/dep.py', 'value = 21\n')
    put(source, 'src/alpha/data.txt', 'fixture')
    result = extract(source, {'source_entrypoints': ['alpha.answer'], 'required_api': [{'path': 'featurelifted.answer', 'kind': 'function'}]}, out)
    assert not result['unresolved_api']
    assert 'alpha.dep' in result['selected_modules']
    assert result['copied_resources']
    # Execute synthetic fixture only, with no source tree on sys.path.
    child = subprocess.run([sys.executable, '-I', '-c', f'import sys; sys.path.insert(0,{str(out)!r}); import featurelifted; assert featurelifted.answer() == 42'], capture_output=True, text=True)
    assert child.returncode == 0, child.stderr


def test_unicode_semicolon_and_alias_imports():
    source = 'x = "é"; import pkg.child as p\nimport os, pkg.child\n'
    got, n = rewrite_imports(source, {'pkg': '_dse_p0'})
    assert n == 2
    assert 'x = "é";' in got
    assert 'import featurelifted._dse_p0.child as p' in got
    assert 'import featurelifted._dse_p0 as pkg' in got
    compile(got, '<fixture>', 'exec')


def test_no_stub_for_renamed_destination_api(tmp_path):
    put(tmp_path / 'source', 'up.py', 'def original():\n    return 1\n')
    out = tmp_path / 'out'
    r = extract(tmp_path / 'source', {'source_entrypoints': ['up.original'], 'required_api': [{'path': 'featurelifted.renamed', 'kind': 'function'}]}, out)
    assert r['unresolved_api'] == {'renamed': 'no_same_name_static_binding'}
    assert 'NotImplementedError' not in (out / 'featurelifted/__init__.py').read_text()
    assert 'renamed' not in (out / 'featurelifted/__init__.py').read_text()


def test_nested_src_layout_and_source_prefix(tmp_path):
    put(tmp_path, 'backend/src/pkg/core.py', 'class A: pass\n')
    assert SourceIndex(tmp_path).resolve('src.pkg.core.A') == ('pkg.core', ('A',))


def test_source_declared_namespace_layout(tmp_path):
    put(tmp_path, '__init__.py', '_package_data = dict(full_package_name="parent.child")\nfrom .core import A\n')
    put(tmp_path, 'core.py', 'class A: pass\n')
    assert SourceIndex(tmp_path).resolve('parent.child.A') == ('parent.child.core', ('A',))


def test_star_reexport_obeys_literal_all(tmp_path):
    put(tmp_path, 'pkg/__init__.py', 'from .core import *\n')
    put(tmp_path, 'pkg/core.py', '__all__ = ["A"]\nclass A: pass\nclass B: pass\n')
    index = SourceIndex(tmp_path)
    assert index.resolve('pkg.A') == ('pkg.core', ('A',))
    assert index.resolve('pkg.B') is None


def test_dynamic_all_is_not_guessed(tmp_path):
    put(tmp_path, 'pkg/__init__.py', 'from .core import *\n')
    put(tmp_path, 'pkg/core.py', '__all__ = make_exports()\nclass A: pass\n')
    assert SourceIndex(tmp_path).resolve('pkg.A') is None


def test_ambiguous_module_layout_is_not_guessed(tmp_path):
    put(tmp_path, 'one/src/pkg.py', 'value = 1\n')
    put(tmp_path, 'two/src/pkg.py', 'value = 2\n')
    index = SourceIndex(tmp_path)
    assert 'pkg' in index.ambiguous
    assert index.resolve('pkg.value') is None


def test_relative_dependency_and_dynamic_import_untouched(tmp_path):
    src = tmp_path / 'source'
    put(src, 'pkg/__init__.py', 'from .core import answer\n')
    put(src, 'pkg/core.py', 'from .dep import value\nimport importlib\ndef answer():\n    return importlib.import_module("pkg.dep").value + value\n')
    put(src, 'pkg/dep.py', 'value = 1\n')
    r = extract(src, {'source_entrypoints': ['pkg.answer'], 'required_api': [{'path': 'featurelifted.answer', 'kind': 'function'}]}, tmp_path / 'out')
    assert 'pkg.dep' in r['selected_modules']
    assert any(x['kind'] == 'dynamic_import_or_resource_call_unmodified' for x in r['diagnostics'])


def test_refuses_to_overwrite(tmp_path):
    import pytest
    with pytest.raises(FileExistsError):
        extract(tmp_path, {}, tmp_path)


def test_explicit_init_path_and_class_init_are_distinct(tmp_path):
    put(tmp_path, 'pkg/__init__.py', 'def hook(): pass\nclass A:\n    def __init__(self): pass\n')
    index = SourceIndex(tmp_path)
    assert index.resolve('pkg.__init__.hook') == ('pkg', ('hook',))
    assert index.resolve('pkg.A.__init__') == ('pkg', ('A', '__init__'))


def test_inherited_entrypoint_across_reexports(tmp_path):
    put(tmp_path, 'pkg/__init__.py', 'from .child import Child\n')
    put(tmp_path, 'pkg/child.py', 'from .base import Parent as Base\nclass Child(Base): pass\n')
    put(tmp_path, 'pkg/base.py', 'class Parent:\n    def operation(self): return 1\n')
    assert SourceIndex(tmp_path).resolve('pkg.Child.operation') == ('pkg.base', ('Parent', 'operation'))


def test_nested_local_and_multiple_inheritance_not_guessed(tmp_path):
    put(tmp_path, 'pkg.py', 'class A:\n    def method(self):\n        def absent(): pass\nclass B: pass\nclass C(A, B): pass\n')
    index = SourceIndex(tmp_path)
    assert index.resolve('pkg.A.absent') is None
    assert index.resolve('pkg.C.method') is None


def test_reviewed_alias_preserves_callable_without_wrapper(tmp_path):
    source = tmp_path / 'source'
    put(source, 'up.py', 'def original(value):\n    return value\n')
    spec = {'source_entrypoints': ['up.original'], 'required_api': [{'path': 'featurelifted.renamed', 'kind': 'function'}]}
    out = tmp_path / 'out'
    result = extract(source, spec, out, reviewed_aliases={'renamed': 'up.original'})
    assert result['reviewed_aliases_applied'] == {'renamed': 'up.original'}
    assert not result['unresolved_api']
    code = (out / 'featurelifted/__init__.py').read_text()
    assert 'import original as renamed' in code and 'def ' not in code


def test_reviewed_alias_cannot_export_method_or_overwrite(tmp_path):
    import pytest
    source = tmp_path / 'source'
    put(source, 'up.py', 'class A:\n    def method(self): pass\ndef original(): pass\n')
    spec = {'source_entrypoints': ['up.original'], 'required_api': [{'path': 'featurelifted.renamed', 'kind': 'function'}]}
    with pytest.raises(ValueError, match='top-level'):
        extract(source, spec, tmp_path / 'out', reviewed_aliases={'renamed': 'up.A.method'})
    spec['required_api'][0]['path'] = 'featurelifted.original'
    with pytest.raises(ValueError, match='unresolved'):
        extract(source, spec, tmp_path / 'out2', reviewed_aliases={'original': 'up.original'})
