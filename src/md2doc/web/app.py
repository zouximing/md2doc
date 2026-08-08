"""md2doc FastAPI Web 应用。

提供单页界面：上传 .md / 在线编辑 / 服务端实时预览 / 下载 .docx。
"""

from __future__ import annotations

import argparse

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="md2doc-web", version="0.1.0")


@app.get("/")
def index() -> dict:
    """占位响应；Task 4 替换为静态单页 HTML。"""
    return {"name": "md2doc-web"}


def main() -> None:
    """md2doc-web CLI 入口：启动 uvicorn 服务。"""
    parser = argparse.ArgumentParser(prog="md2doc-web")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
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
