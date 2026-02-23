from kgbuilder.core import exceptions


def test_document_load_error_properties():
    err = exceptions.DocumentLoadError("file.txt", "not found")
    assert isinstance(err, exceptions.KGBuilderError)
    assert "file.txt" in str(err)
    assert err.path == "file.txt"
    assert err.reason == "not found"


def test_unsupported_format_error_message():
    err = exceptions.UnsupportedFormatError(".xyz")
    assert "Unsupported format" in str(err)


def test_llm_error_is_kgbuilder_error():
    le = exceptions.LLMError("oops")
    assert isinstance(le, exceptions.KGBuilderError)
    assert str(le) == "oops"
