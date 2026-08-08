"""md2doc.web.schemas 与 dependencies 的单元测试。"""

import pytest

from md2doc.web.dependencies import (
    CONVERSION_FAILED,
    DEPENDENCY_MISSING,
    FILE_TOO_LARGE,
    INTERNAL,
    INVALID_INPUT,
    MAX_BODY_BYTES,
    UNSUPPORTED_TYPE,
    WebError,
    sanitize_filename,
)
from md2doc.web.schemas import ConvertRequest, PreviewRequest, PreviewResponse, UploadResponse

# --- schemas ---

def test_upload_response_basic():
    r = UploadResponse(text="hello", filename="a.md")
    assert r.text == "hello"
    assert r.filename == "a.md"


def test_preview_request_text_required():
    with pytest.raises(ValueError):
        PreviewRequest()  # type: ignore[call-arg]


def test_preview_response_html():
    r = PreviewResponse(html="<p>hi</p>")
    assert r.html == "<p>hi</p>"


def test_convert_request_filename_optional():
    r = ConvertRequest(text="x")
    assert r.text == "x"
    assert r.filename is None


def test_convert_request_with_filename():
    r = ConvertRequest(text="x", filename="doc.md")
    assert r.filename == "doc.md"


# --- 错误码常量 ---

def test_error_codes_are_strings():
    assert INVALID_INPUT == "INVALID_INPUT"
    assert FILE_TOO_LARGE == "FILE_TOO_LARGE"
    assert UNSUPPORTED_TYPE == "UNSUPPORTED_TYPE"
    assert DEPENDENCY_MISSING == "DEPENDENCY_MISSING"
    assert CONVERSION_FAILED == "CONVERSION_FAILED"
    assert INTERNAL == "INTERNAL"


def test_max_body_bytes_is_10mb():
    assert MAX_BODY_BYTES == 10 * 1024 * 1024


# --- WebError ---

def test_web_error_attributes():
    err = WebError(code=FILE_TOO_LARGE, detail="太大", status_code=413)
    assert err.code == FILE_TOO_LARGE
    assert err.detail == "太大"
    assert err.status_code == 413
    assert str(err) == "太大"


# --- sanitize_filename ---

def test_sanitize_none_returns_none():
    assert sanitize_filename(None) is None


def test_sanitize_empty_returns_none():
    assert sanitize_filename("") is None


def test_sanitize_plain_name():
    assert sanitize_filename("report.md") == "report"


def test_sanitize_no_extension():
    assert sanitize_filename("report") == "report"


def test_sanitize_strips_path_separators():
    # 防止路径遍历：Path 会把 .. 解析为父目录组件，
    # Path("../evil.md").name == "evil.md"，stem == "evil"，
    # 因此 sanitize 后返回 "evil"（无路径分隔符可替换）。
    assert sanitize_filename("../evil.md") == "evil"
    assert sanitize_filename("..\\evil.md") == "evil"


def test_sanitize_strips_special_chars():
    assert sanitize_filename('a<b> c:"d|.md') == "a_b_ c__d_"


def test_sanitize_strips_dots_only():
    assert sanitize_filename("...md") is None  # stem 全是点


def test_sanitize_truncates_long_name():
    name = "a" * 200 + ".md"
    result = sanitize_filename(name)
    assert result is not None
    assert len(result) == 80
