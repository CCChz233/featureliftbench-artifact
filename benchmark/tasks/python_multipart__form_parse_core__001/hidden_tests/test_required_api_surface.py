"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Field,
    File,
    FormParser,
    parse_form,
    create_form_parser,
    parse_options_header,
    exceptions,
)


def test_required_api_surface():
    assert isinstance(Field, type)
    assert isinstance(File, type)
    assert isinstance(FormParser, type)
    assert hasattr(FormParser, 'write')
    assert hasattr(FormParser, 'finalize')
    assert callable(parse_form)
    assert callable(create_form_parser)
    assert callable(parse_options_header)
    assert exceptions is not None
    assert issubclass(getattr(exceptions, 'FormParserError'), BaseException)
    assert issubclass(getattr(exceptions, 'MultipartParseError'), BaseException)
