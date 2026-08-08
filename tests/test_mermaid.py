import pytest
from md2doc import mermaid
from md2doc.mermaid import MermaidBlock


# --- has_mermaid ---

def test_has_mermaid_false_for_plain_text():
    assert mermaid.has_mermaid("没有图的普通文本") is False


def test_has_mermaid_true_for_backtick_fence():
    md = "```mermaid\ngraph TD\nA-->B\n```"
    assert mermaid.has_mermaid(md) is True


def test_has_mermaid_true_for_tilde_fence():
    md = "~~~mermaid\ngraph TD\nA-->B\n~~~"
    assert mermaid.has_mermaid(md) is True


def test_has_mermaid_case_insensitive():
    md = "```Mermaid\ngraph TD\nA-->B\n```"
    assert mermaid.has_mermaid(md) is True


def test_has_mermaid_false_for_other_code_blocks():
    md = "```python\nprint(1)\n```"
    assert mermaid.has_mermaid(md) is False


# --- extract_blocks ---

def test_extract_blocks_returns_empty_for_plain_text():
    assert mermaid.extract_blocks("普通文本") == []


def test_extract_blocks_finds_single_block():
    md = "```mermaid\ngraph TD\nA-->B\n```"
    blocks = mermaid.extract_blocks(md)
    assert len(blocks) == 1
    assert isinstance(blocks[0], MermaidBlock)
    assert "graph TD" in blocks[0].code
    assert "A-->B" in blocks[0].code


def test_extract_blocks_assigns_sequential_ids():
    md = (
        "```mermaid\ngraph TD\nA-->B\n```\n"
        "文本\n"
        "```mermaid\ngraph LR\nC-->D\n```"
    )
    blocks = mermaid.extract_blocks(md)
    assert [b.id for b in blocks] == ["mermaid_0", "mermaid_1"]


def test_extract_blocks_sets_span_positions():
    md = "前缀\n```mermaid\ngraph TD\nA-->B\n```\n后缀"
    blocks = mermaid.extract_blocks(md)
    assert len(blocks) == 1
    # 验证 start/end 精确覆盖整个围栏块（含开闭围栏）
    span = md[blocks[0].start:blocks[0].end]
    assert span.startswith("```mermaid")
    assert span.endswith("```")
    assert "graph TD" in span


def test_extract_blocks_does_not_match_python_blocks():
    md = "```python\nprint(1)\n```"
    assert mermaid.extract_blocks(md) == []


def test_extract_blocks_handles_tilde_fence():
    md = "~~~mermaid\ngraph TD\nA-->B\n~~~"
    blocks = mermaid.extract_blocks(md)
    assert len(blocks) == 1
    assert "graph TD" in blocks[0].code


def test_extract_blocks_from_fixture_file():
    from pathlib import Path
    fixture = Path(__file__).parent / "fixtures" / "multi_mermaid.md"
    md = fixture.read_text(encoding="utf-8")
    blocks = mermaid.extract_blocks(md)
    assert len(blocks) == 3  # 两个反引号 + 一个 tilde
    assert [b.id for b in blocks] == ["mermaid_0", "mermaid_1", "mermaid_2"]
