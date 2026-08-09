"""程序化生成 src/md2doc/templates/reference.docx 样式模板。

开发期工具：手动运行以重新生成模板。不要在运行时调用。

用法：
    python scripts/build_reference_docx.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

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


def _set_line_spacing(style_element, lines: float, before_pt: float | None = None, after_pt: float | None = None) -> None:
    """行距 + 可选段前/段后间距。

    lines=1.5 → line=360 twips, lineRule=auto。
    before_pt/after_pt 单位为 pt（1pt=20 twips）。
    """
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
    if before_pt is not None:
        spc.set(qn("w:before"), str(int(before_pt * 20)))
    if after_pt is not None:
        spc.set(qn("w:after"), str(int(after_pt * 20)))


def _set_color(style_element, hex_rgb: str) -> None:
    rPr = style_element.find(qn("w:rPr"))
    if rPr is None:
        rPr = style_element.makeelement(qn("w:rPr"), {})
        style_element.append(rPr)
    color = rPr.find(qn("w:color"))
    if color is None:
        color = rPr.makeelement(qn("w:color"), {})
        rPr.append(color)
    color.set(qn("w:val"), hex_rgb)


def _set_left_indent(style_element, cm: float) -> None:
    """左缩进（单位 cm，1cm=567 twips）。"""
    pPr = style_element.find(qn("w:pPr"))
    if pPr is None:
        pPr = style_element.makeelement(qn("w:pPr"), {})
        style_element.append(pPr)
    ind = pPr.find(qn("w:ind"))
    if ind is None:
        ind = pPr.makeelement(qn("w:ind"), {})
        pPr.append(ind)
    ind.set(qn("w:left"), str(int(cm * 567)))


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

    # First Paragraph 额外有段前 9pt
    first_para = doc.styles["First Paragraph"]
    _set_line_spacing(first_para.element, 1.5, before_pt=9)

    # --- Compact（列表项，无缩进）---
    compact = _find_or_create_style(doc, "Compact")
    _set_east_asia(compact.element, "宋体")
    _set_size(compact.element, 12)
    _set_line_spacing(compact.element, 1.0, before_pt=3, after_pt=3)

    # --- Block Text（引用块）---
    block = _find_or_create_style(doc, "Block Text")
    _set_east_asia(block.element, "宋体")
    _set_size(block.element, 10.5)
    _set_line_spacing(block.element, 1.0, after_pt=10)

    # --- Source Code（代码块）---
    code = _find_or_create_style(doc, "Source Code")
    _set_ascii_font(code.element, "Consolas")
    _set_size(code.element, 10)
    _set_color(code.element, "404040")
    _set_left_indent(code.element, 0.5)

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
