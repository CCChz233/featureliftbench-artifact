"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Converter,
    structure,
    unstructure,
    errors,
    gen,
)


def test_required_api_surface():
    assert isinstance(Converter, type)
    assert hasattr(Converter, 'structure')
    assert hasattr(Converter, 'register_structure_hook')
    assert hasattr(Converter, 'register_unstructure_hook')
    assert hasattr(Converter, 'unstructure')
    assert callable(structure)
    assert callable(unstructure)
    assert errors is not None
    assert issubclass(getattr(errors, 'ClassValidationError'), BaseException)
    assert issubclass(getattr(errors, 'ForbiddenExtraKeysError'), BaseException)
    assert gen is not None
    assert callable(getattr(gen, 'make_dict_structure_fn'))
    assert callable(getattr(gen, 'make_dict_unstructure_fn'))
    assert callable(getattr(gen, 'override'))
