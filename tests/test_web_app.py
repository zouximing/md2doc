"""md2doc.web.app 路由测试。

使用 starlette TestClient（基于 httpx）。所有外部调用走 monkeypatch。
"""

import pytest
from fastapi.testclient import TestClient

from md2doc.web.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_index_returns_placeholder(client):
    """GET / 返回 200，Task 1 阶段为 JSON 占位。"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"name": "md2doc-web"}
