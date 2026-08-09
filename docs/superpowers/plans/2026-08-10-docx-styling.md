# docx 输出格式化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 md2doc 在转换 .md 到 .docx 时，自动应用统一的字体/字号/段落样式，给标题自动编号，给图片和表格自动加中文 caption（"图 N"、"表 N"）。

**Architecture:** 用 pandoc 原生的 `--reference-doc` 传 reference.docx 样式模板，用 `--lua-filter` 注入 caption 编号，用 `--number-sections` 给标题自动编号。converter 在调用 pandoc 前剥离 md 源里手写的标题编号避免双重编号。

**Tech Stack:** Python 3.9+, pandoc, python-docx（仅 dev 依赖，用于生成 reference.docx 和测试验证）, Lua 5.x（pandoc 内置）。

**Spec:** [`docs/superpowers/specs/2026-08-10-docx-styling-design.md`](../specs/2026-08-10-docx-styling-design.md)

---

## File Structure

| 文件 | 动作 | 责任 |
|---|---|---|
| `src/md2doc/templates/reference.docx` | 新建 | docx 样式模板（字体/字号/段落/caption 居中） |
| `src/md2doc/templates/caption.lua` | 新建 | Lua filter：图片加 "图 N: "、表格加 "表 N" |
| `scripts/build_reference_docx.py` | 新建 | 程序化生成 reference.docx 的脚本（开发期工具） |
| `src/md2doc/pandoc.py` | 修改 | `convert()` 增加 `reference_doc` / `lua_filter` / `number_sections` 参数 |
| `src/md2doc/converter.py` | 修改 | 加 `strip_heading_numbers()`；`convert_file()` / `convert_batch()` 加 `styled` 参数 |
| `src/md2doc/cli.py` | 修改 | 加 `--no-style` 开关 |
| `pyproject.toml` | 修改 | 加 python-docx dev 依赖；声明 templates 为 package data |
| `tests/test_pandoc.py` | 修改 | 加参数构造测试 |
| `tests/test_converter.py` | 修改 | 加 `strip_heading_numbers` 单测 + convert_file styled 测试 |
| `tests/test_cli.py` | 修改 | 加 `--no-style` 测试 |
| `tests/test_integration_styled.py` | 新建 | @pytest.mark.integration 端到端验证 |

---

## Task 1: `strip_heading_numbers` 函数

剥离 md 源标题里手写的章节编号。仅作用于临时 staged.md，不动用户源文件。

**Files:**
- Modify: `src/md2doc/converter.py`
- Test: `tests/test_converter.py`

- [ ] **Step 1: 在 tests/test_converter.py 末尾追加失败测试**

把以下代码追加到 `tests/test_converter.py` 末尾（不要替换文件）：

```python
# --- strip_heading_numbers ---

@pytest.mark.parametrize(
    "line,expected",
    [
        ("## 1. 基础文本元素", "## 基础文本元素"),
        ("### 1.1 段落与换行", "### 段落与换行"),
        ("#### 2.1.1.1 四级标题", "#### 四级标题"),
        ("# md2doc 全面测试文档", "# md2doc 全面测试文档"),
        ("## 1 一些章节", "## 一些章节"),
        ("## 1.2.3. 变长编号", "## 变长编号"),
        ("## 1.5英寸是多大", "## 1.5英寸是多大"),  # 数字后无空格，不剥
        ("## 第一章 概述", "## 第一章 概述"),
        ("## 标题（注释）", "## 标题（注释）"),
        ("普通段落 1. 内容", "普通段落 1. 内容"),  # 非标题不剥
    ],
)
def test_strip_heading_numbers_single_line(line, expected):
    assert converter.strip_heading_numbers(line) == expected


def test_strip_heading_numbers_preserves_other_content():
    md = "# 标题\n\n## 1.1 章节\n\n普通段落。\n\n### 2.3.4 深层\n"
    expected = "# 标题\n\n## 章节\n\n普通段落。\n\n### 深层\n"
    assert converter.strip_heading_numbers(md) == expected
```

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_converter.py::test_strip_heading_numbers_single_line tests/test_converter.py::test_strip_heading_numbers_preserves_other_content -v
```

预期：FAIL，错误信息含 `module 'md2doc.converter' has no attribute 'strip_heading_numbers'`。

- [ ] **Step 3: 在 converter.py 顶部 import 区加 `import re`**

文件顶部 `from __future__ import annotations` 之后、其它 import 之前，已有 `import tempfile` 等。在 `import tempfile` 这一行下方加一行：

```python
import re
```

（若已有则跳过）

- [ ] **Step 4: 在 converter.py 加 `strip_heading_numbers` 函数**

在 `from md2doc.errors import InvalidInputError` 之后、`def scan_md_files` 之前，插入：

```python
_HEADING_NUM_PATTERN = re.compile(
    r"^(#{1,6})\s+(?:\d+(?:\.\d+)*)\.?\s+(.+)$",
    re.MULTILINE,
)


def strip_heading_numbers(md: str) -> str:
    """剥离 Markdown 标题里手写的章节编号。

    仅作用于 ``#`` 开头的标题行，且要求"数字 + 可选小数点 + 空格 + 文本"模式。
    "## 1. xxx" → "## xxx"，"### 1.2.3 yyy" → "### yyy"。
    无编号或非"数字."开头的标题不动。

    Args:
        md: 原始 Markdown 文本。

    Returns:
        标题编号被剥离后的文本。
    """
    return _HEADING_NUM_PATTERN.sub(r"\1 \2", md)
```

- [ ] **Step 5: 运行测试，确认通过**

```
pytest tests/test_converter.py::test_strip_heading_numbers_single_line tests/test_converter.py::test_strip_heading_numbers_preserves_other_content -v
```

预期：PASS（10 个 parametrize case + 1 个多行 case 全过）。

- [ ] **Step 6: 提交**

```bash
git add src/md2doc/converter.py tests/test_converter.py
git commit -m "feat(converter): 新增 strip_heading_numbers 剥离标题手写编号"
```

---

## Task 2: `pandoc.convert()` 扩展参数

`convert()` 增加三个 keyword-only 参数：`reference_doc`、`lua_filter`、`number_sections`。仅影响命令行参数构造。

**Files:**
- Modify: `src/md2doc/pandoc.py`
- Test: `tests/test_pandoc.py`

- [ ] **Step 1: 在 tests/test_pandoc.py 末尾追加失败测试**

```python
def test_convert_with_reference_doc_and_lua_filter_and_numbering(monkeypatch, tmp_path):
    """三个 styled 参数全部传入时，args 应包含对应的 pandoc 选项。"""
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("md2doc.pandoc.shutil.which", lambda name: "/usr/bin/pandoc")
    monkeypatch.setattr("md2doc.pandoc.subprocess.run", fake_run)

    ref = tmp_path / "ref.docx"
    ref.write_bytes(b"")
    lua = tmp_path / "cap.lua"
    lua.write_text("--", encoding="utf-8")
    input_md = tmp_path / "in.md"
    input_md.write_text("# hi", encoding="utf-8")

    pandoc.convert(
        input_md,
        tmp_path / "out.docx",
        "docx",
        reference_doc=ref,
        lua_filter=lua,
        number_sections=True,
    )

    assert f"--reference-doc={ref}" in captured["args"]
    assert f"--lua-filter={lua}" in captured["args"]
    assert "--number-sections" in captured["args"]


def test_convert_with_no_styled_options_matches_legacy_args(monkeypatch, tmp_path):
    """三个参数都不传时，args 应当与旧调用完全一致（向后兼容）。"""
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = list(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("md2doc.pandoc.shutil.which", lambda name: "/usr/bin/pandoc")
    monkeypatch.setattr("md2doc.pandoc.subprocess.run", fake_run)

    input_md = tmp_path / "in.md"
    input_md.write_text("# hi", encoding="utf-8")
    pandoc.convert(input_md, tmp_path / "out.docx", "docx")

    expected = [
        "/usr/bin/pandoc",
        str(input_md),
        "-o",
        str(tmp_path / "out.docx"),
        "--from=markdown",
        "--to=docx",
    ]
    assert captured["args"] == expected


def test_convert_partial_styled_options(monkeypatch, tmp_path):
    """只传 number_sections 时，args 不应含 reference-doc / lua-filter。"""
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("md2doc.pandoc.shutil.which", lambda name: "/usr/bin/pandoc")
    monkeypatch.setattr("md2doc.pandoc.subprocess.run", fake_run)

    input_md = tmp_path / "in.md"
    input_md.write_text("# hi", encoding="utf-8")
    pandoc.convert(input_md, tmp_path / "out.docx", "docx", number_sections=True)

    assert "--number-sections" in captured["args"]
    assert not any(a.startswith("--reference-doc") for a in captured["args"])
    assert not any(a.startswith("--lua-filter") for a in captured["args"])
```

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_pandoc.py::test_convert_with_reference_doc_and_lua_filter_and_numbering tests/test_pandoc.py::test_convert_with_no_styled_options_matches_legacy_args tests/test_pandoc.py::test_convert_partial_styled_options -v
```

预期：FAIL，错误信息含 `unexpected keyword argument 'reference_doc'`。

- [ ] **Step 3: 修改 `src/md2doc/pandoc.py` 的 `convert()` 函数**

把 `def convert(input_path: str | Path, output_path: str | Path, fmt: str) -> None:` 整个函数（含 docstring 和实现）替换为：

```python
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
```

- [ ] **Step 4: 运行测试，确认全部通过**

```
pytest tests/test_pandoc.py -v
```

预期：所有用例 PASS（包括既有用例和新加的 3 个）。

- [ ] **Step 5: 提交**

```bash
git add src/md2doc/pandoc.py tests/test_pandoc.py
git commit -m "feat(pandoc): convert() 加 reference_doc/lua_filter/number_sections 参数"
```

---

## Task 3: 生成 `reference.docx` 模板

用脚本程序化生成 reference.docx，模板包含设计规格 3.1 节定义的全部样式。

**Files:**
- Create: `scripts/build_reference_docx.py`
- Create: `src/md2doc/templates/__init__.py`
- Create: `src/md2doc/templates/reference.docx`（脚本生成）

- [ ] **Step 1: 创建 `scripts/` 目录并写脚本**

在仓库根目录创建 `scripts/build_reference_docx.py`：

```python
"""程序化生成 src/md2doc/templates/reference.docx 样式模板。

开发期工具：手动运行以重新生成模板。不要在运行时调用。

用法：
    python scripts/build_reference_docx.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Twips

OUTPUT = Path(__file__).resolve().parent.parent / "src" / "md2doc" / "templates" / "reference.docx"


def _set_east_asia(style_element, font_name: str) -> None:
    """给样式元素设置 eastAsia 字体（中文）。"""
    rPr = style_element.find(qn("w:rPr"))
    if rPr is None:
        rPr = style_element.makeelement(qn("w:rPr"), {})
        style_element.append(rPr)
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = rPr.makeelement(qn("w:rFonts"), {})
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), font_name)


def _set_ascii_font(style_element, font_name: str) -> None:
    rPr = style_element.find(qn("w:rPr"))
    if rPr is None:
        rPr = style_element.makeelement(qn("w:rPr"), {})
        style_element.append(rPr)
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = rPr.makeelement(qn("w:rFonts"), {})
        rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), font_name)
    rFonts.set(qn("w:hAnsi"), font_name)


def _set_size(style_element, pt: float) -> None:
    rPr = style_element.find(qn("w:rPr"))
    if rPr is None:
        rPr = style_element.makeelement(qn("w:rPr"), {})
        style_element.append(rPr)
    sz = rPr.find(qn("w:sz"))
    if sz is None:
        sz = rPr.makeelement(qn("w:sz"), {})
        rPr.append(sz)
    sz.set(qn("w:val"), str(int(pt * 2)))


def _set_bold(style_element, bold: bool = True) -> None:
    rPr = style_element.find(qn("w:rPr"))
    if rPr is None:
        rPr = style_element.makeelement(qn("w:rPr"), {})
        style_element.append(rPr)
    b = rPr.find(qn("w:b"))
    if b is None:
        b = rPr.makeelement(qn("w:b"), {})
        rPr.append(b)
    # 删除 on/off 元素，确保 b 标签存在即可表示加粗
    b.set(qn("w:val"), "1" if bold else "0")


def _set_outline_level(style_element, level: int) -> None:
    pPr = style_element.find(qn("w:pPr"))
    if pPr is None:
        pPr = style_element.makeelement(qn("w:pPr"), {})
        style_element.append(pPr)
    outline = pPr.find(qn("w:outlineLvl"))
    if outline is None:
        outline = pPr.makeelement(qn("w:outlineLvl"), {})
        pPr.append(outline)
    outline.set(qn("w:val"), str(level))


def _set_centered(style_element) -> None:
    pPr = style_element.find(qn("w:pPr"))
    if pPr is None:
        pPr = style_element.makeelement(qn("w:pPr"), {})
        style_element.append(pPr)
    jc = pPr.find(qn("w:jc"))
    if jc is None:
        jc = pPr.makeelement(qn("w:jc"), {})
        pPr.append(jc)
    jc.set(qn("w:val"), "center")


def _set_first_line_indent_chars(style_element, chars: int) -> None:
    """首行缩进 N 个字符（按 Word 字符单位）。"""
    pPr = style_element.find(qn("w:pPr"))
    if pPr is None:
        pPr = style_element.makeelement(qn("w:pPr"), {})
        style_element.append(pPr)
    ind = pPr.find(qn("w:ind"))
    if ind is None:
        ind = pPr.makeelement(qn("w:ind"), {})
        pPr.append(ind)
    ind.set(qn("w:firstLineChars"), str(chars * 100))


def _set_line_spacing(style_element, lines: float) -> None:
    """1.5 倍行距 = 360 twips（240 * lines）。"""
    pPr = style_element.find(qn("w:pPr"))
    if pPr is None:
        pPr = style_element.makeelement(qn("w:pPr"), {})
        style_element.append(pPr)
    spc = pPr.find(qn("w:spacing"))
    if spc is None:
        spc = pPr.makeelement(qn("w:spacing"), {})
        pPr.append(spc)
    spc.set(qn("w:line"), str(int(240 * lines)))
    spc.set(qn("w:lineRule"), "auto")


def _set_color(style_element, hex_rgb: str) -> None:
    rPr = style_element.find(qn("w:rPr"))
    if rPr is None:
        rPr = rPr = style_element.makeelement(qn("w:rPr"), {})
        style_element.append(rPr)
    color = rPr.find(qn("w:color"))
    if color is None:
        color = rPr.makeelement(qn("w:color"), {})
        rPr.append(color)
    color.set(qn("w:val"), hex_rgb)


def _find_or_create_style(doc, name: str, style_type=1):
    """1 = PARAGRAPH_STYLE。"""
    for s in doc.styles:
        if s.name == name and s.type == style_type:
            return s
    return doc.styles.add_style(name, style_type)


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()

    # --- Normal（正文）---
    normal = doc.styles["Normal"]
    _set_east_asia(normal.element, "宋体")
    _set_ascii_font(normal.element, "Times New Roman")
    _set_size(normal.element, 12)

    # --- Title（文档标题）---
    title = _find_or_create_style(doc, "Title")
    _set_east_asia(title.element, "黑体")
    _set_size(title.element, 18)
    _set_bold(title.element, True)

    # --- Heading 1-6 ---
    heading_sizes = [18, 16, 14, 12, 12, 12]
    for i, sz in enumerate(heading_sizes, start=1):
        h = _find_or_create_style(doc, f"Heading {i}")
        _set_east_asia(h.element, "黑体")
        _set_size(h.element, sz)
        _set_bold(h.element, True)
        _set_outline_level(h.element, i - 1)

    # --- Body Text / First Paragraph（正文段落，首行缩进 + 1.5 行距）---
    for name in ("Body Text", "First Paragraph"):
        s = _find_or_create_style(doc, name)
        _set_east_asia(s.element, "宋体")
        _set_size(s.element, 12)
        _set_first_line_indent_chars(s.element, 2)
        _set_line_spacing(s.element, 1.5)

    # --- Compact（列表项，无缩进）---
    compact = _find_or_create_style(doc, "Compact")
    _set_east_asia(compact.element, "宋体")
    _set_size(compact.element, 12)

    # --- Block Text（引用块）---
    block = _find_or_create_style(doc, "Block Text")
    _set_east_asia(block.element, "宋体")
    _set_size(block.element, 10.5)

    # --- Source Code（代码块）---
    code = _find_or_create_style(doc, "Source Code")
    _set_ascii_font(code.element, "Consolas")
    _set_size(code.element, 10)
    _set_color(code.element, "404040")

    # --- Image Caption / Table Caption（图/表标题，居中 + 黑体 10.5pt）---
    for name in ("Image Caption", "Table Caption"):
        cap = _find_or_create_style(doc, name)
        _set_east_asia(cap.element, "黑体")
        _set_size(cap.element, 10.5)
        _set_centered(cap.element)

    doc.save(OUTPUT)
    print(f"已生成：{OUTPUT}")
    print(f"大小：{OUTPUT.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 创建 templates 包**

创建空文件 `src/md2doc/templates/__init__.py`（内容只有一行 docstring）：

```python
"""md2doc 内置资源（reference.docx 样式模板、caption.lua 过滤器）。"""
```

- [ ] **Step 3: 安装 python-docx（若未装）并运行脚本**

```bash
pip install python-docx
python scripts/build_reference_docx.py
```

预期：输出 `已生成：.../src/md2doc/templates/reference.docx` 和文件大小（几 KB）。

- [ ] **Step 4: 在 tests/ 加模板校验测试**

创建 `tests/test_reference_template.py`：

```python
"""验证 reference.docx 模板包含设计要求的全部样式。"""

from pathlib import Path

import pytest

try:
    from docx import Document
except ImportError:  # python-docx 未装时跳过
    pytest.skip("python-docx 未安装", allow_module_level=True)

from docx.oxml.ns import qn

TEMPLATE = Path(__file__).resolve().parent.parent / "src" / "md2doc" / "templates" / "reference.docx"


@pytest.fixture(scope="module")
def doc():
    return Document(str(TEMPLATE))


def _east_asia(style) -> str | None:
    rPr = style.element.find(qn("w:rPr"))
    if rPr is None:
        return None
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        return None
    return rFonts.get(qn("w:eastAsia"))


def _size(style) -> int | None:
    rPr = style.element.find(qn("w:rPr"))
    if rPr is None:
        return None
    sz = rPr.find(qn("w:sz"))
    if sz is None:
        return None
    return int(sz.get(qn("w:val"))) // 2


def test_normal_is_songti_12pt(doc):
    s = doc.styles["Normal"]
    assert _east_asia(s) == "宋体"
    assert _size(s) == 12


@pytest.mark.parametrize("name,size", [
    ("Heading 1", 18), ("Heading 2", 16), ("Heading 3", 14),
    ("Heading 4", 12), ("Heading 5", 12), ("Heading 6", 12),
])
def test_headings_are_heiti_bold(doc, name, size):
    s = doc.styles[name]
    assert _east_asia(s) == "黑体"
    assert _size(s) == size


def test_title_is_heiti_18pt(doc):
    s = doc.styles["Title"]
    assert _east_asia(s) == "黑体"
    assert _size(s) == 18


def test_image_caption_is_centered(doc):
    s = doc.styles["Image Caption"]
    pPr = s.element.find(qn("w:pPr"))
    jc = pPr.find(qn("w:jc")) if pPr is not None else None
    assert jc is not None and jc.get(qn("w:val")) == "center"
    assert _east_asia(s) == "黑体"
    assert _size(s) == 10.5


def test_table_caption_is_centered(doc):
    s = doc.styles["Table Caption"]
    pPr = s.element.find(qn("w:pPr"))
    jc = pPr.find(qn("w:jc")) if pPr is not None else None
    assert jc is not None and jc.get(qn("w:val")) == "center"
```

- [ ] **Step 5: 运行模板校验**

```
pytest tests/test_reference_template.py -v
```

预期：全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add scripts/build_reference_docx.py src/md2doc/templates/__init__.py src/md2doc/templates/reference.docx tests/test_reference_template.py
git commit -m "feat(templates): 程序化生成 reference.docx 样式模板"
```

---

## Task 4: `caption.lua` Lua filter

处理图片和表格的中文 caption 编号注入。

**Files:**
- Create: `src/md2doc/templates/caption.lua`

- [ ] **Step 1: 创建 Lua filter 文件**

在 `src/md2doc/templates/caption.lua` 写入：

```lua
-- caption.lua: 给图片和表格自动加中文 caption 编号。
-- 图片：原 caption 前加 "图 N: "；表格：caption 设为 "表 N"。
-- 序号按文档出现顺序，单文档内连续。

local img_count = 0
local tbl_count = 0

-- 处理 Figure 元素（pandoc >= 2.10，带 caption 的图片为 Figure）
function Figure(el)
    img_count = img_count + 1
    local prefix = pandoc.Str(string.format("图 %d: ", img_count))
    if el.caption and el.caption.long and #el.caption.long > 0 then
        local first_block = el.caption.long[1]
        if first_block and first_block.content then
            -- 把 prefix 插到第一个 block 的 inline 列表最前面
            table.insert(first_block.content, 1, prefix)
        end
    end
    return el
end

-- 处理 Table 元素
function Table(el)
    tbl_count = tbl_count + 1
    local cap_text = string.format("表 %d", tbl_count)
    -- el.caption 是 pandoc.Caption（含 .long 和 .short）
    if el.caption then
        el.caption.long = pandoc.List({pandoc.Plain({pandoc.Str(cap_text)})})
        el.caption.short = pandoc.List({pandoc.Str(cap_text)})
    end
    return el
end
```

- [ ] **Step 2: 用一个最小 md 手工验证 lua 语法（不进入测试套件）**

```bash
echo '# 测试

![示例图](nonexistent.png)

| a | b |
|---|---|
| 1 | 2 |
' > /tmp/_cap_test.md

pandoc /tmp/_cap_test.md -o /tmp/_cap_test.docx --lua-filter=src/md2doc/templates/caption.lua 2>&1 || echo "(pandoc 未装时跳过)"
```

预期：pandoc 输出无 lua 语法错误。若 pandoc 未装则跳过（接受）。

- [ ] **Step 3: 提交**

```bash
git add src/md2doc/templates/caption.lua
git commit -m "feat(templates): 新增 caption.lua 注入图表中文编号"
```

---

## Task 5: 改 `converter.py` 接入模板

`convert_file()` 和 `convert_batch()` 加 `styled` 参数，默认 True。styled=True + fmt=docx 时启用 reference_doc / lua_filter / number_sections，并对 md 调用 `strip_heading_numbers`。

**Files:**
- Modify: `src/md2doc/converter.py`
- Test: `tests/test_converter.py`

- [ ] **Step 1: 在 tests/test_converter.py 末尾追加失败测试**

```python
# --- convert_file / convert_batch 的 styled 参数 ---

def test_convert_file_styled_docx_passes_all_template_args(tmp_path, monkeypatch):
    """styled=True 且 fmt=docx 时，应调用 pandoc.convert 传入三个参数 + 剥离编号。"""
    captured = {}

    def fake_pandoc_convert(input_path, output_path, fmt, **kwargs):
        captured["kwargs"] = kwargs
        captured["input_content"] = Path(input_path).read_text(encoding="utf-8")

    input_md = tmp_path / "in.md"
    input_md.write_text("## 1.1 章节\n\n内容\n", encoding="utf-8")

    monkeypatch.setattr("md2doc.converter.pandoc.convert", fake_pandoc_convert)
    monkeypatch.setattr("md2doc.converter.mermaid.preprocess", lambda md, d: md)

    converter.convert_file(input_md, tmp_path / "out.docx", "docx", no_mermaid=True, styled=True)

    assert captured["kwargs"].get("reference_doc") is not None
    assert captured["kwargs"].get("lua_filter") is not None
    assert captured["kwargs"].get("number_sections") is True
    # 标题编号已被剥离
    assert "## 章节" in captured["input_content"]
    assert "## 1.1" not in captured["input_content"]


def test_convert_file_unstyled_skips_template_args(tmp_path, monkeypatch):
    """styled=False 时，pandoc.convert 不应收到任何 styled 参数。"""
    captured = {}

    def fake_pandoc_convert(input_path, output_path, fmt, **kwargs):
        captured["kwargs"] = kwargs
        captured["input_content"] = Path(input_path).read_text(encoding="utf-8")

    input_md = tmp_path / "in.md"
    input_md.write_text("## 1.1 章节\n", encoding="utf-8")

    monkeypatch.setattr("md2doc.converter.pandoc.convert", fake_pandoc_convert)
    monkeypatch.setattr("md2doc.converter.mermaid.preprocess", lambda md, d: md)

    converter.convert_file(input_md, tmp_path / "out.docx", "docx", no_mermaid=True, styled=False)

    assert captured["kwargs"] == {}
    # 标题编号未剥离
    assert "## 1.1 章节" in captured["input_content"]


def test_convert_file_styled_non_docx_skips_template_args(tmp_path, monkeypatch):
    """styled=True 但 fmt != docx 时，pandoc 不收 styled 参数（reference.docx 只对 docx 生效）。"""
    captured = {}

    def fake_pandoc_convert(input_path, output_path, fmt, **kwargs):
        captured["kwargs"] = kwargs

    input_md = tmp_path / "in.md"
    input_md.write_text("# hi\n", encoding="utf-8")

    monkeypatch.setattr("md2doc.converter.pandoc.convert", fake_pandoc_convert)
    monkeypatch.setattr("md2doc.converter.mermaid.preprocess", lambda md, d: md)

    converter.convert_file(input_md, tmp_path / "out.html", "html", no_mermaid=True, styled=True)

    assert captured["kwargs"] == {}
```

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_converter.py::test_convert_file_styled_docx_passes_all_template_args tests/test_converter.py::test_convert_file_unstyled_skips_template_args tests/test_converter.py::test_convert_file_styled_non_docx_skips_template_args -v
```

预期：FAIL，错误含 `unexpected keyword argument 'styled'`。

- [ ] **Step 3: 修改 converter.py 的 `convert_file()` 函数**

把 `def convert_file(...)` 整个函数（含 docstring）替换为：

```python
def _template_path(name: str) -> Path:
    """返回包内 templates 目录下指定资源的路径。"""
    return Path(__file__).parent / "templates" / name


def convert_file(
    input_file: Path,
    output_file: Path,
    fmt: str,
    no_mermaid: bool = False,
    styled: bool = True,
) -> Path:
    """转换单个 .md 文件到目标格式。

    流程：读源 MD -> mermaid 预处理（除非 no_mermaid）-> 可选剥离标题编号
        -> 写临时 .md -> pandoc 转换 -> 输出。

    Args:
        input_file: 输入 .md 文件路径。
        output_file: 输出文件路径。
        fmt: 目标格式（如 'docx'）。
        no_mermaid: True 则跳过 mermaid 预处理。
        styled: True 且 fmt=docx 时启用 reference.docx 样式模板、caption.lua
            图表编号、--number-sections 标题自动编号。False 则完全使用 pandoc 默认输出。

    Returns:
        输出文件路径。

    Raises:
        MmdcNotFoundError: MD 含 mermaid 但 mmdc 未装（由 mermaid.preprocess 抛出）。
        ConversionError: pandoc 或 mmdc 执行失败。
    """
    input_file = Path(input_file)
    md = input_file.read_text(encoding="utf-8")

    # 预处理在临时目录中进行，不污染源文件所在目录
    with tempfile.TemporaryDirectory(prefix="md2doc_") as tmpdir:
        if no_mermaid:
            processed = md
        else:
            processed = mermaid.preprocess(md, Path(tmpdir))

        # 构建 pandoc 调用参数
        kwargs: dict = {}
        if styled:
            processed = strip_heading_numbers(processed)
            if fmt == "docx":
                kwargs["reference_doc"] = _template_path("reference.docx")
                kwargs["lua_filter"] = _template_path("caption.lua")
                kwargs["number_sections"] = True

        # 写入临时 .md 文件交给 pandoc
        staged = Path(tmpdir) / "_staged.md"
        staged.write_text(processed, encoding="utf-8")
        pandoc.convert(staged, output_file, fmt, **kwargs)

    return Path(output_file)
```

- [ ] **Step 4: 修改 converter.py 的 `convert_batch()` 函数签名和调用**

把现有的 `convert_batch(...)` 函数签名加 `styled: bool = True` 参数，并在内部 `convert_file` 调用处透传。具体修改：

旧签名：

```python
def convert_batch(
    input_files: list[Path],
    output_dir: Path,
    fmt: str,
    base_input_dir: Path,
    no_mermaid: bool = False,
) -> tuple[list[Path], list[tuple[Path, Exception]]]:
```

新签名：

```python
def convert_batch(
    input_files: list[Path],
    output_dir: Path,
    fmt: str,
    base_input_dir: Path,
    no_mermaid: bool = False,
    styled: bool = True,
) -> tuple[list[Path], list[tuple[Path, Exception]]]:
```

旧调用：

```python
            actual_output = convert_file(
                input_file, output_file, fmt, no_mermaid=no_mermaid
            )
```

新调用：

```python
            actual_output = convert_file(
                input_file, output_file, fmt,
                no_mermaid=no_mermaid, styled=styled,
            )
```

- [ ] **Step 5: 运行测试，确认通过**

```
pytest tests/test_converter.py -v
```

预期：全部 PASS（包括新加的 3 个和既有的全部）。

- [ ] **Step 6: 提交**

```bash
git add src/md2doc/converter.py tests/test_converter.py
git commit -m "feat(converter): convert_file/batch 加 styled 参数接入模板"
```

---

## Task 6: CLI 加 `--no-style` 开关

**Files:**
- Modify: `src/md2doc/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: 在 tests/test_cli.py 末尾追加失败测试**

```python
def test_no_style_flag_disables_styling(tmp_path, monkeypatch):
    """--no-style 时 convert_file 应当收到 styled=False。"""
    captured = {}

    def fake_convert_file(input_file, output_file, fmt, **kwargs):
        captured["styled"] = kwargs.get("styled", True)
        Path(output_file).write_bytes(b"")
        return Path(output_file)

    monkeypatch.setattr("md2doc.cli.converter.convert_file", fake_convert_file)
    runner = CliRunner()
    src = tmp_path / "a.md"
    src.write_text("# a", encoding="utf-8")

    result = runner.invoke(main, [str(src), "-o", str(tmp_path / "out.docx"), "--no-style"])

    assert result.exit_code == 0, result.output
    assert captured["styled"] is False


def test_default_invocation_enables_styling(tmp_path, monkeypatch):
    """不带 --no-style 时 convert_file 应当收到 styled=True。"""
    captured = {}

    def fake_convert_file(input_file, output_file, fmt, **kwargs):
        captured["styled"] = kwargs.get("styled", True)
        Path(output_file).write_bytes(b"")
        return Path(output_file)

    monkeypatch.setattr("md2doc.cli.converter.convert_file", fake_convert_file)
    runner = CliRunner()
    src = tmp_path / "a.md"
    src.write_text("# a", encoding="utf-8")

    result = runner.invoke(main, [str(src), "-o", str(tmp_path / "out.docx")])

    assert result.exit_code == 0, result.output
    assert captured["styled"] is True
```

如果 tests/test_cli.py 顶部没有 `from click.testing import CliRunner` 和 `from md2doc.cli import main`，先确认这两个 import 是否已在文件中（若没有则补上）。

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_cli.py::test_no_style_flag_disables_styling tests/test_cli.py::test_default_invocation_enables_styling -v
```

预期：FAIL（`--no-style` 不存在），错误含 `no such option: --no-style` 或 `styled` 永远是 True。

- [ ] **Step 3: 修改 cli.py 加 `--no-style` 选项**

在 `@click.option("--no-mermaid", ...)` 这行下方加一行：

```python
@click.option("--no-style", is_flag=True, default=False, help="不应用 docx 样式模板（reference.docx + 自动编号 + caption），使用 pandoc 默认输出")
```

然后修改 `def main(...)` 函数签名加 `no_style` 参数：

旧签名：

```python
def main(input, output, fmt, recursive, no_mermaid, show_version):
```

新签名：

```python
def main(input, output, fmt, recursive, no_mermaid, no_style, show_version):
```

- [ ] **Step 4: 修改 cli.py 中 `_convert_single` 和 `_convert_directory` 函数**

把 `_convert_single` 改为：

```python
def _convert_single(input_path, output, fmt, no_mermaid, no_style):
    output_file = converter.resolve_output_path(
        input_path, Path(output) if output else None, fmt, is_batch=False
    )
    converter.convert_file(
        input_path, output_file, fmt,
        no_mermaid=no_mermaid, styled=not no_style,
    )
    _console.print(f"[green]✓[/green] {input_path} → {output_file}")
```

把 `_convert_directory` 的函数签名加 `no_style` 参数，并在 `convert_batch` 调用处透传：

旧签名：

```python
def _convert_directory(input_path, output, fmt, recursive, no_mermaid):
```

新签名：

```python
def _convert_directory(input_path, output, fmt, recursive, no_mermaid, no_style):
```

旧调用：

```python
    successes, failures = converter.convert_batch(
        files, output_dir, fmt, base_input_dir=input_path, no_mermaid=no_mermaid
    )
```

新调用：

```python
    successes, failures = converter.convert_batch(
        files, output_dir, fmt, base_input_dir=input_path,
        no_mermaid=no_mermaid, styled=not no_style,
    )
```

- [ ] **Step 5: 修改 main 中调用 _convert_single / _convert_directory 的地方**

main 函数体中：

旧：

```python
        if not is_batch:
            _convert_single(input_path, output, fmt, no_mermaid)
        else:
            _convert_directory(input_path, output, fmt, recursive, no_mermaid)
```

新：

```python
        if not is_batch:
            _convert_single(input_path, output, fmt, no_mermaid, no_style)
        else:
            _convert_directory(input_path, output, fmt, recursive, no_mermaid, no_style)
```

- [ ] **Step 6: 运行 CLI 测试，确认通过**

```
pytest tests/test_cli.py -v
```

预期：全部 PASS。

- [ ] **Step 7: 提交**

```bash
git add src/md2doc/cli.py tests/test_cli.py
git commit -m "feat(cli): 加 --no-style 开关"
```

---

## Task 7: pyproject.toml 配置

声明 templates 为 package data，加 python-docx 为 dev 依赖。

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 在 pyproject.toml 的 `[project.optional-dependencies]` dev 列表中加 python-docx**

找到：

```toml
dev = [
    "pytest>=8.0",
    "pytest-cov",
    "ruff",
    "httpx>=0.27",
]
```

改为：

```toml
dev = [
    "pytest>=8.0",
    "pytest-cov",
    "ruff",
    "httpx>=0.27",
    "python-docx>=1.0",
]
```

- [ ] **Step 2: 在 pyproject.toml 中加 `[tool.hatch.build.targets.wheel.force-include]` 配置**

在 `[tool.hatch.build.targets.wheel]` 那一段下方（不要替换原有内容）加：

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/md2doc/templates/reference.docx" = "md2doc/templates/reference.docx"
"src/md2doc/templates/caption.lua" = "md2doc/templates/caption.lua"
```

（注意：`packages = ["src/md2doc"]` 已经会把整个包目录打进 wheel，但 templates 子目录的 docx/lua 资源在某些 hatchling 版本下需要 force-include 兜底。）

- [ ] **Step 3: 重新安装并验证模板能被包找到**

```bash
pip install -e .
python -c "from md2doc.converter import _template_path; p = _template_path('reference.docx'); print(p); print('exists:', p.exists())"
```

预期：打印路径 `.../src/md2doc/templates/reference.docx` 和 `exists: True`。

- [ ] **Step 4: 提交**

```bash
git add pyproject.toml
git commit -m "build: 声明 templates 资源 + python-docx dev 依赖"
```

---

## Task 8: 端到端集成测试

把所有改动串起来，用真实 pandoc 生成 docx，用 python-docx 读回验证关键样式。

**Files:**
- Create: `tests/test_integration_styled.py`

- [ ] **Step 1: 创建测试文件**

```python
"""端到端集成测试：md → docx 的样式实际生效。

需要真实 pandoc 和 python-docx。默认通过 pytest marker 'integration' 跳过，
显式运行：pytest tests/test_integration_styled.py -m integration -v
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

try:
    from docx import Document
except ImportError:
    pytest.skip("python-docx 未安装", allow_module_level=True)

from docx.oxml.ns import qn

from md2doc import converter, pandoc

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "simple.md"


@pytest.fixture(scope="module")
def generated_docx(tmp_path_factory):
    if pandoc.get_version() is None:
        pytest.skip("pandoc 未安装")
    out = tmp_path_factory.mktemp("out") / "result.docx"
    converter.convert_file(FIXTURE, out, "docx", no_mermaid=True, styled=True)
    return Document(str(out))


def _east_asia(style) -> str | None:
    rPr = style.element.find(qn("w:rPr"))
    if rPr is None:
        return None
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        return None
    return rFonts.get(qn("w:eastAsia"))


def test_headings_use_heiti(generated_docx):
    """至少一个 Heading 段落字体为黑体。"""
    heading_styles = {
        s.name for s in generated_docx.styles
        if s.name and s.name.startswith("Heading")
    }
    found_heiti = False
    for name in heading_styles:
        s = generated_docx.styles[name]
        if _east_asia(s) == "黑体":
            found_heiti = True
            break
    assert found_heiti, "未找到 eastAsia=黑体 的 Heading 样式"


def test_image_caption_and_table_caption_styles_exist(generated_docx):
    """生成的 docx 应包含 Image Caption 和 Table Caption 样式。"""
    names = {s.name for s in generated_docx.styles if s.name}
    assert "Image Caption" in names
    assert "Table Caption" in names


def test_number_sections_applied(generated_docx):
    """pandoc --number-sections 应在标题前注入数字。simple.md 中应能找到形如 '1 xxx' 的标题段落。"""
    import re
    found = False
    for p in generated_docx.paragraphs:
        if p.style and p.style.name and p.style.name.startswith("Heading"):
            if re.match(r"^\d+(\.\d+)*\s", p.text):
                found = True
                break
    assert found, f"未找到自动编号的标题，所有标题文本：{[p.text for p in generated_docx.paragraphs if p.style and p.style.name and p.style.name.startswith('Heading')]}"
```

- [ ] **Step 2: 确认 simple.md fixture 存在并包含至少一个标题和一个图片**

```
cat tests/fixtures/simple.md
```

如果 simple.md 不包含图片或表格，集成测试中的 `test_image_caption_and_table_caption_styles_exist` 仍能 PASS（pandoc 会从 reference.docx 继承样式定义），但 `test_number_sections_applied` 需要至少一个 Heading。若 simple.md 没有 Heading，则改用 `full_test.md`（项目内已确认存在）。

如果要用 full_test.md，把测试文件的 `FIXTURE` 改为：

```python
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "full_test.md"
```

- [ ] **Step 3: 运行集成测试**

```
pytest tests/test_integration_styled.py -m integration -v
```

预期：3 个用例 PASS（前提：pandoc 已装、reference.docx 已生成）。

- [ ] **Step 4: 跑完整测试套件确认没有回归**

```
pytest -v
```

预期：所有非 integration 用例 PASS（默认 addopts 排除 integration）。

- [ ] **Step 5: 提交**

```bash
git add tests/test_integration_styled.py
git commit -m "test(integration): 端到端验证 docx 样式生效"
```

---

## 完工后的手动验收（可选）

```bash
# 用一个真实 md 转换并肉眼检查
python -m md2doc tests/fixtures/full_test.md -o /tmp/full_test_styled.docx
# 打开 /tmp/full_test_styled.docx 检查：
# - 标题用黑体、自动编号（1, 1.1, 1.1.1）
# - 正文用宋体、首行缩进 2 字符
# - 表格下方有"表 1, 表 2, 表 3"居中黑体 caption
# - Mermaid 图下方有"图 1: 图, 图 2: 图, ..."居中黑体 caption
```
