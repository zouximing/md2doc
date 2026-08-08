"""mermaid 代码块的提取、渲染、替换。

这是项目中唯一与 mmdc 交互的模块。提取/替换是纯字符串操作，
渲染调用外部 mmdc 工具。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from md2doc.errors import ConversionError, MmdcNotFoundError

# 匹配 ```mermaid 和 ~~~mermaid 两种围栏，大小写不敏感
_PATTERN = re.compile(
    r"^(?P<fence>```|~~~)[ \t]*mermaid[ \t]*\n"
    r"(?P<code>.*?)"
    r"^(?P=fence)[ \t]*$",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


@dataclass
class MermaidBlock:
    """一个 mermaid 代码块的提取结果。"""

    id: str
    code: str
    start: int
    end: int
    image_path: Path | None = None


def has_mermaid(md: str) -> bool:
    """判断 md 中是否包含 mermaid 代码块。"""
    return _PATTERN.search(md) is not None


def extract_blocks(md: str) -> list[MermaidBlock]:
    """从 md 中提取所有 mermaid 代码块，按出现顺序编号。"""
    blocks = []
    for idx, match in enumerate(_PATTERN.finditer(md)):
        blocks.append(
            MermaidBlock(
                id=f"mermaid_{idx}",
                code=match.group("code"),
                start=match.start(),
                end=match.end(),
            )
        )
    return blocks


def replace_blocks(
    md: str, blocks: list[MermaidBlock], image_paths: list[Path]
) -> str:
    """把 md 中的 mermaid 代码块替换为图片引用。

    按 start 位置从后往前替换，避免位置偏移。
    image_paths 顺序需与 blocks 顺序一致。

    Args:
        md: 原始 Markdown 文本。
        blocks: extract_blocks 的返回值。
        image_paths: 每个块对应的渲染后 PNG 绝对路径。

    Returns:
        替换后的 Markdown 文本。
    """
    if not blocks:
        return md
    if len(blocks) != len(image_paths):
        raise ValueError(
            f"blocks 与 image_paths 长度不一致（{len(blocks)} != {len(image_paths)}）"
        )
    # 按位置从后往前替换，避免位置偏移
    # 注意：调用方负责传绝对路径（见 render_all 的输出）
    sorted_items = sorted(
        zip(blocks, image_paths), key=lambda x: x[0].start, reverse=True
    )
    result = md
    for block, image_path in sorted_items:
        replacement = f"![图]({image_path.as_posix()})"
        result = result[: block.start] + replacement + result[block.end:]
    return result


_MMDC_INSTALL_HINT = (
    "未找到 mmdc（mermaid-cli）。请安装：\n"
    "  npm install -g @mermaid-js/mermaid-cli"
)

# 各平台 Chrome/Chromium 标准路径。用于绕过 puppeteer 自带 Chromium
# 在某些 Windows 环境下的启动崩溃（STATUS_ACCESS_VIOLATION）。
_CHROME_PATHS: dict[str, list[str]] = {
    "win32": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ],
    "darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ],
}


def _linux_chrome_candidates() -> list[str]:
    """Linux 上 Chrome/Chromium 常见路径。"""
    return [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ]


def _find_system_chrome() -> str | None:
    """查找系统已安装的 Chrome/Chromium 可执行文件路径。

    Returns:
        找到的可执行文件绝对路径；找不到返回 None。
    """
    if sys.platform == "win32":
        candidates: list[str] = list(_CHROME_PATHS.get("win32", []))
    elif sys.platform == "darwin":
        candidates = list(_CHROME_PATHS.get("darwin", []))
    else:
        candidates = _linux_chrome_candidates()
    for path in candidates:
        if Path(path).is_file():
            return path
    return None


def _build_mmdc_env() -> dict[str, str] | None:
    """构造传给 mmdc 的环境变量。

    策略：
    1. 用户已设 PUPPETEER_EXECUTABLE_PATH 环境变量 → 优先尊重，原样继承
    2. 否则查找系统 Chrome，找到则注入到 env
    3. 都没有 → 返回 None（让 subprocess 继承当前环境，由 mmdc 默认行为处理）

    Returns:
        env dict（含 PUPPETEER_EXECUTABLE_PATH）或 None。
    """
    env = dict(os.environ)
    if env.get("PUPPETEER_EXECUTABLE_PATH"):
        return env
    chrome = _find_system_chrome()
    if chrome is not None:
        env["PUPPETEER_EXECUTABLE_PATH"] = chrome
        return env
    return None


def ensure_mmdc() -> str:
    """返回 mmdc 可执行路径。未安装则抛 MmdcNotFoundError。"""
    path = shutil.which("mmdc")
    if path is None:
        raise MmdcNotFoundError(_MMDC_INSTALL_HINT)
    return path


def get_version() -> str | None:
    """返回 mmdc 版本号字符串。未安装返回 None。"""
    if shutil.which("mmdc") is None:
        return None
    result = subprocess.run(
        ["mmdc", "--version"], capture_output=True, text=True, check=False, timeout=30
    )
    return result.stdout.strip() or None


def render_all(blocks: list[MermaidBlock], out_dir: Path) -> list[Path]:
    """把所有 mermaid 块渲染为 PNG 图片。

    为每个块在 out_dir 中写一个 .mmd 源文件，调用 mmdc 渲染为 PNG。
    返回值：每个块对应的 PNG 路径列表（顺序与 blocks 一致）。

    Raises:
        MmdcNotFoundError: mmdc 未安装。
        ConversionError: 某个块的渲染失败（错误信息含块 ID 和 mmdc 输出）。
    """
    if not blocks:
        return []
    mmdc_path = ensure_mmdc()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # 注入 Chrome 路径，避免 puppeteer 自带 Chromium 在某些环境下崩溃
    env = _build_mmdc_env()

    image_paths: list[Path] = []
    for block in blocks:
        mmd_file = out_dir / f"{block.id}.mmd"
        png_file = out_dir / f"{block.id}.png"
        mmd_file.write_text(block.code, encoding="utf-8")

        args = [
            mmdc_path,
            "-i", str(mmd_file),
            "-o", str(png_file),
            "--scale", "2",
        ]
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
            env=env,
        )
        if result.returncode != 0:
            detail = (result.stderr + result.stdout).strip()
            raise ConversionError(
                f"mermaid 渲染失败（块 {block.id}）：\n{detail}"
            )
        image_paths.append(png_file)
    return image_paths


def preprocess(md: str, work_dir: Path) -> str:
    """高层封装：如果 md 含 mermaid，提取->渲染->替换；否则原样返回。

    Args:
        md: 原始 Markdown 文本。
        work_dir: 用于存放中间 .mmd 和 .png 文件的目录。

    Returns:
        处理后的 Markdown 文本。若无 mermaid 块则与输入相同。

    Raises:
        MmdcNotFoundError: md 含 mermaid 但 mmdc 未安装。
        ConversionError: 某个 mermaid 块渲染失败。
    """
    if not has_mermaid(md):
        return md
    blocks = extract_blocks(md)
    image_paths = render_all(blocks, Path(work_dir))
    return replace_blocks(md, blocks, image_paths)
