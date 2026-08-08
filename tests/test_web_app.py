"""md2doc.web.app 路由测试。

使用 starlette TestClient（基于 httpx）。所有外部调用走 monkeypatch。
"""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from md2doc.errors import ConversionError, DependencyNotFoundError
from md2doc.web.app import app


@pytest.fixture
def client():
    return TestClient(app)


def _fake_pandoc_convert_writes_html(input_path, output_path, fmt):
    """模拟 pandoc：把输入读入，包一层 <p> 写到输出。"""
    text = Path(input_path).read_text(encoding="utf-8")
    Path(output_path).write_text(f"<p>{text}</p>", encoding="utf-8")


def _fake_pandoc_convert_writes_docx(input_path, output_path, fmt):
    """模拟 pandoc 写 docx：写固定字节。"""
    Path(output_path).write_bytes(b"PK\x03\x04DOCX")


# --- GET / ---


def test_index_returns_html(client):
    """GET / 返回 HTML 单页（含编辑器占位元素）。"""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<div id=\"editor\"" in response.text
    assert "<div id=\"preview\"" in response.text


# --- POST /api/upload ---


def test_upload_md_returns_text_and_filename(client):
    """成功上传 .md 返回 text 与 filename。"""
    response = client.post(
        "/api/upload",
        files={"file": ("hello.md", io.BytesIO(b"# Hello"), "text/markdown")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "# Hello"
    assert data["filename"] == "hello.md"


def test_upload_rejects_non_md_extension(client):
    """非 .md 扩展名返回 415 UNSUPPORTED_TYPE。"""
    response = client.post(
        "/api/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hi"), "text/plain")},
    )
    assert response.status_code == 415
    assert response.json()["code"] == "UNSUPPORTED_TYPE"


def test_upload_rejects_uppercase_md_extension(client):
    """大写 .MD 也接受（大小写不敏感）。"""
    response = client.post(
        "/api/upload",
        files={"file": ("README.MD", io.BytesIO(b"# Hi"), "text/markdown")},
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "README.MD"


def test_upload_rejects_oversized_file(client):
    """超过 MAX_BODY_BYTES 返回 413。"""
    from md2doc.web.dependencies import MAX_BODY_BYTES

    big = b"x" * (MAX_BODY_BYTES + 1)
    response = client.post(
        "/api/upload",
        files={"file": ("big.md", io.BytesIO(big), "text/markdown")},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"


def test_upload_rejects_invalid_utf8(client):
    """非 UTF-8 内容返回 400 INVALID_INPUT。"""
    response = client.post(
        "/api/upload",
        files={"file": ("bad.md", io.BytesIO(b"\xff\xfe\xfd"), "text/markdown")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_INPUT"


# --- POST /api/preview ---


def test_preview_returns_html(client, monkeypatch):
    """成功预览返回 html。"""
    monkeypatch.setattr(
        "md2doc.web.app.pandoc.convert", _fake_pandoc_convert_writes_html
    )
    response = client.post("/api/preview", json={"text": "hello"})
    assert response.status_code == 200
    assert response.json()["html"] == "<p>hello</p>"


def test_preview_does_not_call_mermaid(client, monkeypatch):
    """预览路径不调用 mermaid.preprocess。"""
    called = {"mermaid": False}

    def fake_preprocess(md, work_dir):
        called["mermaid"] = True
        return md

    monkeypatch.setattr(
        "md2doc.web.app.pandoc.convert", _fake_pandoc_convert_writes_html
    )
    monkeypatch.setattr("md2doc.web.app.mermaid.preprocess", fake_preprocess)

    client.post("/api/preview", json={"text": "```mermaid\ngraph TD\nA-->B\n```"})
    assert called["mermaid"] is False


def test_preview_dependency_missing_returns_500(client, monkeypatch):
    """pandoc 未装时返回 500 DEPENDENCY_MISSING。"""
    def raise_dep(*args, **kwargs):
        raise DependencyNotFoundError("pandoc 未装")

    monkeypatch.setattr("md2doc.web.app.pandoc.convert", raise_dep)

    response = client.post("/api/preview", json={"text": "hi"})
    assert response.status_code == 500
    assert response.json()["code"] == "DEPENDENCY_MISSING"


def test_preview_conversion_error_returns_500(client, monkeypatch):
    """pandoc 报错时返回 500 CONVERSION_FAILED。"""
    def raise_conv(*args, **kwargs):
        raise ConversionError("pandoc 失败")

    monkeypatch.setattr("md2doc.web.app.pandoc.convert", raise_conv)

    response = client.post("/api/preview", json={"text": "hi"})
    assert response.status_code == 500
    assert response.json()["code"] == "CONVERSION_FAILED"


def test_preview_rejects_oversized_text(client):
    """text 超过 MAX_BODY_BYTES 返回 413。"""
    from md2doc.web.dependencies import MAX_BODY_BYTES

    text = "x" * (MAX_BODY_BYTES + 1)
    response = client.post("/api/preview", json={"text": text})
    assert response.status_code == 413


# --- POST /api/convert ---


def test_convert_returns_docx_bytes(client, monkeypatch):
    """成功转换返回 docx 字节。"""
    monkeypatch.setattr(
        "md2doc.web.app.converter.convert_file",
        lambda inp, outp, fmt, no_mermaid=False: Path(outp).write_bytes(b"DOCX"),
    )
    response = client.post("/api/convert", json={"text": "# Hello"})
    assert response.status_code == 200
    assert response.content == b"DOCX"
    assert "wordprocessingml.document" in response.headers["content-Type".lower()]
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('.docx"')


def test_convert_uses_filename_when_provided(client, monkeypatch):
    """filename 提供时进入 Content-Disposition。"""
    monkeypatch.setattr(
        "md2doc.web.app.converter.convert_file",
        lambda inp, outp, fmt, no_mermaid=False: Path(outp).write_bytes(b"DOCX"),
    )
    response = client.post(
        "/api/convert", json={"text": "# Hi", "filename": "my-report.md"}
    )
    assert response.status_code == 200
    assert '"my-report.docx"' in response.headers["content-disposition"]


def test_convert_calls_mermaid_for_mermaid_content(client, monkeypatch):
    """convert 路径委托给 converter.convert_file 且 no_mermaid=False。

    注：mermaid.preprocess 由 converter.convert_file 内部调用（见 converter.py）。
    本测试把 converter.convert_file mock 掉，因此无法直接观测 mermaid 调用；
    改为断言 convert 路径调用 converter.convert_file 时传 no_mermaid=False，
    确保把 mermaid 渲染能力交给 converter（而非像 preview 路径跳过 mermaid）。
    """
    captured = {}

    def fake_convert_file(inp, outp, fmt, no_mermaid=False):
        captured["no_mermaid"] = no_mermaid
        Path(outp).write_bytes(b"DOCX")

    monkeypatch.setattr("md2doc.web.app.converter.convert_file", fake_convert_file)

    response = client.post(
        "/api/convert", json={"text": "```mermaid\ngraph TD\nA-->B\n```"}
    )
    assert response.status_code == 200
    assert captured.get("no_mermaid") is False


def test_convert_dependency_missing_returns_500(client, monkeypatch):
    """pandoc/mmdc 未装返回 500。"""
    def fail(*args, **kwargs):
        raise DependencyNotFoundError("missing")

    monkeypatch.setattr("md2doc.web.app.converter.convert_file", fail)
    response = client.post("/api/convert", json={"text": "hi"})
    assert response.status_code == 500
    assert response.json()["code"] == "DEPENDENCY_MISSING"


def test_convert_conversion_error_returns_500(client, monkeypatch):
    """转换报错返回 500 CONVERSION_FAILED。"""
    def fail(*args, **kwargs):
        raise ConversionError("fail")

    monkeypatch.setattr("md2doc.web.app.converter.convert_file", fail)
    response = client.post("/api/convert", json={"text": "hi"})
    assert response.status_code == 500
    assert response.json()["code"] == "CONVERSION_FAILED"


def test_convert_sanitize_filename(client, monkeypatch):
    """filename 含特殊字符被清理。"""
    monkeypatch.setattr(
        "md2doc.web.app.converter.convert_file",
        lambda inp, outp, fmt, no_mermaid=False: Path(outp).write_bytes(b"DOCX"),
    )
    response = client.post(
        "/api/convert", json={"text": "x", "filename": "../evil.md"}
    )
    assert response.status_code == 200
    cd = response.headers["content-disposition"]
    assert ".." not in cd  # 路径遍历被清理
    assert cd.endswith('.docx"')


def test_convert_no_filename_uses_default(client, monkeypatch):
    """未提供 filename 时使用默认 document.docx。"""
    monkeypatch.setattr(
        "md2doc.web.app.converter.convert_file",
        lambda inp, outp, fmt, no_mermaid=False: Path(outp).write_bytes(b"DOCX"),
    )
    response = client.post("/api/convert", json={"text": "x"})
    assert response.status_code == 200
    assert '"document.docx"' in response.headers["content-disposition"]


# --- INTERNAL 兜底路径 ---


def test_preview_internal_error_returns_500(client, monkeypatch):
    """未预期异常返回 500 INTERNAL。"""
    def raise_runtime(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("md2doc.web.app.pandoc.convert", raise_runtime)

    response = client.post("/api/preview", json={"text": "hi"})
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"


def test_convert_internal_error_returns_500(client, monkeypatch):
    """未预期异常返回 500 INTERNAL。"""
    def raise_runtime(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("md2doc.web.app.converter.convert_file", raise_runtime)

    response = client.post("/api/convert", json={"text": "hi"})
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"
