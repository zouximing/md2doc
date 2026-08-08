from md2doc.errors import (
    ConversionError,
    DependencyNotFoundError,
    InvalidInputError,
    Md2docError,
    MmdcNotFoundError,
    PandocNotFoundError,
)


def test_base_error_exit_code_is_4():
    assert Md2docError("msg").exit_code == 4


def test_invalid_input_error_exit_code_is_2():
    assert InvalidInputError("msg").exit_code == 2


def test_dependency_not_found_exit_code_is_3():
    assert DependencyNotFoundError("msg").exit_code == 3


def test_pandoc_not_found_is_dependency_subclass():
    err = PandocNotFoundError("missing")
    assert err.exit_code == 3
    assert isinstance(err, DependencyNotFoundError)
    assert isinstance(err, Md2docError)


def test_mmdc_not_found_is_dependency_subclass():
    err = MmdcNotFoundError("missing")
    assert err.exit_code == 3
    assert isinstance(err, DependencyNotFoundError)


def test_conversion_error_exit_code_is_4():
    assert ConversionError("msg").exit_code == 4


def test_all_errors_inherit_from_md2doc_error():
    for cls in [
        InvalidInputError,
        DependencyNotFoundError,
        PandocNotFoundError,
        MmdcNotFoundError,
        ConversionError,
    ]:
        assert issubclass(cls, Md2docError)
