"""mermaid 代码块的提取、渲染、替换。

这是项目中唯一与 mmdc 交互的模块。提取/替换是纯字符串操作，
渲染调用外部 mmdc 工具。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

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
