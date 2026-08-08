"""md2doc-web 端到端集成测试（需要真实 pandoc/mmdc，默认跳过）。

手动运行：python -m pytest -m integration tests/test_web_integration.py -v
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from md2doc.web.app import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.integration
def test_integration_index_returns_html(client):
    """GET / 返回 HTML 单页。"""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div id="editor"' in response.text


@pytest.mark.integration
def test_integration_preview_with_real_pandoc(client):
    """真实 pandoc：预览纯 markdown 成功，html 含渲染后的标题。"""
    response = client.post(
        "/api/preview", json={"text": "# 你好\n\n这是一段文本。"}
    )
    assert response.status_code == 200
    html = response.json()["html"]
    assert "<h1" in html or "你好" in html


@pytest.mark.integration
def test_integration_convert_simple_md(client):
    """真实 pandoc：转换纯文本 markdown 得到非空 docx。"""
    response = client.post(
        "/api/convert", json={"text": "# 你好\n\n测试", "filename": "simple.md"}
    )
    assert response.status_code == 200
    assert response.content[:2] == b"PK"  # docx 是 zip，magic bytes 是 PK
    assert '"simple.docx"' in response.headers["content-disposition"]


@pytest.mark.integration
def test_integration_upload_and_convert(client):
    """端到端：上传 fixtures/with_mermaid.md → 预览 → 下载 docx（需 mmdc）。"""
    fixture = Path(__file__).parent / "fixtures" / "with_mermaid.md"

    # 上传
    with open(fixture, "rb") as f:
        up = client.post(
            "/api/upload",
            files={"file": ("with_mermaid.md", f, "text/markdown")},
        )
    assert up.status_code == 200
    text = up.json()["text"]

    # 预览
    prev = client.post("/api/preview", json={"text": text})
    assert prev.status_code == 200
    assert "html" in prev.json()

    # 下载
    dl = client.post(
        "/api/convert", json={"text": text, "filename": "with_mermaid.md"}
    )
    assert dl.status_code == 200
    assert dl.content[:2] == b"PK"
    assert len(dl.content) > 1000  # docx 不会太小
