"""md2doc-web API 的 Pydantic 请求/响应模型。"""

from typing import Optional

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
    filename: Optional[str] = None  # noqa: FA100 - 保持 Optional 兼容性
