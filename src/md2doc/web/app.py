"""md2doc FastAPI Web 应用。

提供单页界面：上传 .md / 在线编辑 / 服务端实时预览 / 下载 .docx。
"""

from __future__ import annotations

import argparse
import asyncio
import tempfile
from pathlib import Path
from typing import Callable

import uvicorn
from fastapi import FastAPI, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from md2doc import converter, mermaid, pandoc  # noqa: F401 — mermaid 作为 mock 锚点
from md2doc.errors import ConversionError, DependencyNotFoundError
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
from md2doc.web.schemas import (
    ConvertRequest,
    PreviewRequest,
    PreviewResponse,
    UploadResponse,
)

app = FastAPI(title="md2doc-web", version="0.1.0")

_STATIC_DIR = Path(__file__).parent / "static"

if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.exception_handler(WebError)
async def web_error_handler(request, exc: WebError) -> JSONResponse:
    """把 WebError 转换为统一错误 JSON。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


def _check_text_size(text: str) -> None:
    if len(text.encode("utf-8")) > MAX_BODY_BYTES:
        raise WebError(FILE_TOO_LARGE, "文本超过 10MB", 413)


async def _run_blocking(func: Callable[[], object]) -> object:
    """把同步阻塞调用（pandoc/mmdc）放到线程池，并统一异常映射。"""
    try:
        return await asyncio.to_thread(func)
    except DependencyNotFoundError as exc:
        raise WebError(DEPENDENCY_MISSING, str(exc), 500) from exc
    except ConversionError as exc:
        raise WebError(CONVERSION_FAILED, str(exc), 500) from exc
    except Exception as exc:
        raise WebError(INTERNAL, f"未预期错误：{exc}", 500) from exc


@app.get("/")
def index() -> FileResponse:
    """返回单页 HTML。"""
    return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")


@app.post("/api/upload", response_model=UploadResponse)
async def upload(file: UploadFile) -> UploadResponse:
    """上传 .md 文件，返回文本内容与文件名。"""
    filename = file.filename or ""
    if not filename.lower().endswith(".md"):
        raise WebError(UNSUPPORTED_TYPE, "仅支持 .md 文件", 415)

    try:
        content = await file.read()
    except OSError as exc:
        raise WebError(INVALID_INPUT, f"文件读取失败：{exc}", 400) from exc

    if len(content) > MAX_BODY_BYTES:
        raise WebError(FILE_TOO_LARGE, "文件超过 10MB", 413)

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WebError(INVALID_INPUT, f"文件读取失败：{exc}", 400) from exc

    return UploadResponse(text=text, filename=filename)


@app.post("/api/preview", response_model=PreviewResponse)
async def preview(req: PreviewRequest) -> PreviewResponse:
    """跳过 mermaid，用 pandoc 把 markdown 转 HTML 片段返回。"""
    _check_text_size(req.text)

    def run() -> str:
        with tempfile.TemporaryDirectory(prefix="md2doc_preview_") as d:
            staged = Path(d) / "_staged.md"
            staged.write_text(req.text, encoding="utf-8")
            out = Path(d) / "_preview.html"
            pandoc.convert(staged, out, "html")
            return out.read_text(encoding="utf-8")

    html = await _run_blocking(run)
    return PreviewResponse(html=html)


@app.post("/api/convert")
async def convert(req: ConvertRequest) -> Response:
    """走完整流程（含 mermaid 渲染），返回 .docx 文件下载。"""
    _check_text_size(req.text)

    def run() -> bytes:
        with tempfile.TemporaryDirectory(prefix="md2doc_convert_") as d:
            inp = Path(d) / "_input.md"
            inp.write_text(req.text, encoding="utf-8")
            out = Path(d) / "_output.docx"
            converter.convert_file(inp, out, "docx", no_mermaid=False)
            return out.read_bytes()

    data = await _run_blocking(run)
    safe_stem = sanitize_filename(req.filename) or "document"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_stem}.docx"'},
    )


def main() -> None:
    """md2doc-web CLI 入口：启动 uvicorn 服务。"""
    parser = argparse.ArgumentParser(prog="md2doc-web")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="监听地址（默认 0.0.0.0，允许内网其他主机访问；设为 127.0.0.1 仅本机）",
    )
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--reload", action="store_true", help="代码热重载（开发用）")
    args = parser.parse_args()
    uvicorn.run(
        "md2doc.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
