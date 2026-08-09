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


def _size(style) -> float | None:
    rPr = style.element.find(qn("w:rPr"))
    if rPr is None:
        return None
    sz = rPr.find(qn("w:sz"))
    if sz is None:
        return None
    return int(sz.get(qn("w:val"))) / 2


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
