"""md2doc-web 共享依赖：错误码、上限、WebError 异常、文件名清理。"""

from __future__ import annotations

import re
from pathlib import Path

# --- 错误码常量 ---

INVALID_INPUT = "INVALID_INPUT"
FILE_TOO_LARGE = "FILE_TOO_LARGE"
UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"
DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
CONVERSION_FAILED = "CONVERSION_FAILED"
INTERNAL = "INTERNAL"

# --- 大小限制 ---

MAX_BODY_BYTES = 10 * 1024 * 1024  # 10MB


class WebError(Exception):
    """Web 层异常。FastAPI exception_handler 会转换为 JSON 错误响应。

    Attributes:
        code: 错误码字符串常量（如 DEPENDENCY_MISSING）。
        detail: 人类可读错误信息。
        status_code: HTTP 状态码。
    """

    def __init__(self, code: str, detail: str, status_code: int) -> None:
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# Windows/Linux 非法文件名字符（含控制字符）
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str | None) -> str | None:
    """把用户提供的文件名清理为安全的 stem（去扩展名、去路径分隔符、去特殊字符）。

    Returns:
        清理后的 stem，或 None（输入为空或清理后为空）。
    """
    if not name:
        return None
    p = Path(name)
    stem = p.stem if p.suffix else p.name
    # 替换路径分隔符，防止路径遍历
    stem = stem.replace("/", "_").replace("\\", "_")
    stem = _BAD_CHARS.sub("_", stem)
    stem = stem.strip().strip(".") or None
    if stem is None:
        return None
    return stem[:80]
