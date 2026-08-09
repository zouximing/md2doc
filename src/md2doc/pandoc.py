"""pandoc 外部工具封装：检测、版本查询、转换调用。

这是项目中唯一与 pandoc 交互的模块，便于测试时 mock。
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from md2doc.errors import ConversionError, PandocNotFoundError

_INSTALL_HINT = (
    "未找到 pandoc。请安装：\n"
    "  Windows:  winget install --id JohnMacFarlane.Pandoc\n"
    "  macOS:    brew install pandoc\n"
    "  Linux:    sudo apt install pandoc  或  sudo pacman -S pandoc"
)


def ensure_pandoc() -> str:
    """返回 pandoc 可执行路径。未安装则抛 PandocNotFoundError。"""
    path = shutil.which("pandoc")
    if path is None:
        raise PandocNotFoundError(_INSTALL_HINT)
    return path


def get_version() -> str | None:
    """返回 pandoc 版本号字符串（如 '3.1.13'）。未安装返回 None。"""
    if shutil.which("pandoc") is None:
        return None
    result = subprocess.run(
        ["pandoc", "--version"], capture_output=True, text=True, check=False
    )
    # 第一行形如 "pandoc 3.1.13"
    match = re.search(r"pandoc\s+(\S+)", result.stdout)
    return match.group(1) if match else None


def convert(
    input_path: str | Path,
    output_path: str | Path,
    fmt: str,
    *,
    reference_doc: str | Path | None = None,
    lua_filter: str | Path | None = None,
    number_sections: bool = False,
) -> None:
    """调用 pandoc 把 input_path 转为 fmt 格式，输出到 output_path。

    Args:
        input_path: 输入 .md 文件路径（Path 或 str）。
        output_path: 输出文件路径（Path 或 str）。
        fmt: 目标格式，如 'docx'、'pdf'、'html'、'epub'。
        reference_doc: docx 输出时的样式模板路径（对应 pandoc --reference-doc）。
            None 则不传。
        lua_filter: Lua filter 文件路径（对应 pandoc --lua-filter）。None 则不传。
        number_sections: True 时加 --number-sections，给标题自动编号。

    Raises:
        PandocNotFoundError: pandoc 未安装。
        ConversionError: pandoc 以非零退出码返回。
    """
    pandoc_path = ensure_pandoc()
    args = [
        pandoc_path,
        str(input_path),
        "-o",
        str(output_path),
        "--from=markdown",
        f"--to={fmt}",
    ]
    if reference_doc is not None:
        args.append(f"--reference-doc={reference_doc}")
    if lua_filter is not None:
        args.append(f"--lua-filter={lua_filter}")
    if number_sections:
        args.append("--number-sections")
    result = subprocess.run(
        args, capture_output=True, text=True, check=False, timeout=120
    )
    if result.returncode != 0:
        raise ConversionError(
            f"pandoc 转换失败（退出码 {result.returncode}）：\n{result.stderr.strip()}"
        )
