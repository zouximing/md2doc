"""md2doc-web API 的 Pydantic 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """POST /api/upload 成功响应。"""

    text: str
    filename: str


class PreviewRequest(BaseModel):
    """POST /api/preview 请求。"""

    text: str


class PreviewResponse(BaseModel):
    """POST /api/preview 成功响应。"""

    html: str


class ConvertRequest(BaseModel):
    """POST /api/convert 请求。filename 可选。"""

    text: str
    filename: str | None = None
