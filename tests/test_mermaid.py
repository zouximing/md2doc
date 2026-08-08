import subprocess
from pathlib import Path

import pytest

from md2doc import mermaid
from md2doc.errors import ConversionError, MmdcNotFoundError
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


# --- replace_blocks ---

def test_replace_blocks_replaces_all_occurrences():
    md = (
        "前缀\n```mermaid\ngraph TD\nA-->B\n```\n"
        "中间\n"
        "```mermaid\ngraph LR\nC-->D\n```\n后缀"
    )
    blocks = mermaid.extract_blocks(md)
    image_paths = [Path("/tmp/m0.png"), Path("/tmp/m1.png")]
    result = mermaid.replace_blocks(md, blocks, image_paths)
    assert "```mermaid" not in result
    assert "/tmp/m0.png" in result
    assert "/tmp/m1.png" in result
    assert "前缀" in result
    assert "后缀" in result


def test_replace_blocks_uses_absolute_paths():
    md = "```mermaid\ngraph TD\nA-->B\n```"
    blocks = mermaid.extract_blocks(md)
    image_paths = [Path("/abs/m_0.png")]
    result = mermaid.replace_blocks(md, blocks, image_paths)
    assert "/abs/m_0.png" in result


def test_replace_blocks_with_empty_list_returns_unchanged():
    md = "普通文本无图"
    assert mermaid.replace_blocks(md, [], []) == md


def test_replace_blocks_preserves_surrounding_content_order():
    md = "AAA\n```mermaid\ngraph TD\nA-->B\n```\nBBB"
    blocks = mermaid.extract_blocks(md)
    result = mermaid.replace_blocks(md, blocks, [Path("/x.png")])
    # AAA 必须在图片前，BBB 必须在图片后
    assert result.index("AAA") < result.index("/x.png")
    assert result.index("/x.png") < result.index("BBB")


# --- ensure_mmdc ---

def test_ensure_mmdc_returns_path_when_installed(monkeypatch):
    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: "/usr/local/bin/mmdc")
    assert mermaid.ensure_mmdc() == "/usr/local/bin/mmdc"


def test_ensure_mmdc_raises_when_not_installed(monkeypatch):
    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: None)
    with pytest.raises(MmdcNotFoundError) as exc_info:
        mermaid.ensure_mmdc()
    msg = str(exc_info.value)
    assert "mmdc" in msg
    assert "npm install" in msg


# --- get_version ---

def test_get_version_returns_normalized_version(monkeypatch):
    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: "/usr/local/bin/mmdc")
    monkeypatch.setattr(
        "md2doc.mermaid.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="10.6.1\n", stderr=""
        ),
    )
    assert mermaid.get_version() == "10.6.1"


def test_get_version_returns_none_when_not_installed(monkeypatch):
    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: None)
    assert mermaid.get_version() is None


# --- render_all ---

def test_render_all_writes_mmd_files_and_calls_mmdc(monkeypatch, tmp_path):
    """验证 render_all 为每个块写 .mmd 文件并以正确参数调用 mmdc。"""
    captured_calls = []

    def fake_run(args, **kwargs):
        captured_calls.append(args)
        # 模拟 mmdc 生成 png 文件
        out_idx = args.index("-o")
        out_path = Path(args[out_idx + 1])
        out_path.write_bytes(b"PNG_DATA")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: "/usr/local/bin/mmdc")
    monkeypatch.setattr("md2doc.mermaid.subprocess.run", fake_run)

    blocks = [
        MermaidBlock(id="mermaid_0", code="graph TD\nA-->B", start=0, end=0),
        MermaidBlock(id="mermaid_1", code="graph LR\nC-->D", start=0, end=0),
    ]

    paths = mermaid.render_all(blocks, tmp_path)

    assert len(paths) == 2
    # 每个 .mmd 文件应被创建
    assert (tmp_path / "mermaid_0.mmd").exists()
    assert (tmp_path / "mermaid_1.mmd").exists()
    # 检查 mmdc 调用参数
    assert len(captured_calls) == 2
    assert captured_calls[0][0] == "/usr/local/bin/mmdc"
    assert "-i" in captured_calls[0]
    assert "-o" in captured_calls[0]
    assert "--scale" in captured_calls[0]
    assert "2" in captured_calls[0]
    # 返回的路径应是生成的 PNG
    assert all(p.suffix == ".png" for p in paths)


def test_render_all_raises_on_mmdc_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: "/usr/local/bin/mmdc")
    monkeypatch.setattr(
        "md2doc.mermaid.subprocess.run",
        lambda args, **kwargs: subprocess.CompletedProcess(
            args=args, returncode=1, stdout="", stderr="Parse error on line 1"
        ),
    )
    blocks = [MermaidBlock(id="mermaid_0", code="!!!invalid", start=0, end=0)]
    with pytest.raises(ConversionError) as exc_info:
        mermaid.render_all(blocks, tmp_path)
    msg = str(exc_info.value)
    assert "mermaid_0" in msg
    assert "Parse error" in msg


def test_render_all_raises_when_mmdc_not_installed(monkeypatch, tmp_path):
    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: None)
    blocks = [MermaidBlock(id="mermaid_0", code="graph TD", start=0, end=0)]
    with pytest.raises(MmdcNotFoundError):
        mermaid.render_all(blocks, tmp_path)


def test_render_all_empty_blocks_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: "/usr/local/bin/mmdc")
    assert mermaid.render_all([], tmp_path) == []


# --- preprocess（高层封装） ---

def test_preprocess_returns_unchanged_when_no_mermaid(monkeypatch, tmp_path):
    """无 mermaid 时直接返回原 md，不调用 mmdc。"""
    md = "普通文本无图"
    # 即使 mmdc 没装，也应该正常返回
    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: None)
    assert mermaid.preprocess(md, tmp_path) == md


def test_preprocess_raises_when_mermaid_but_mmdc_missing(monkeypatch, tmp_path):
    md = "```mermaid\ngraph TD\nA-->B\n```"
    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: None)
    with pytest.raises(MmdcNotFoundError):
        mermaid.preprocess(md, tmp_path)


def test_preprocess_replaces_blocks_with_images(monkeypatch, tmp_path):
    def fake_run(args, **kwargs):
        out_idx = args.index("-o")
        Path(args[out_idx + 1]).write_bytes(b"PNG")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: "/usr/local/bin/mmdc")
    monkeypatch.setattr("md2doc.mermaid.subprocess.run", fake_run)

    md = "前缀\n```mermaid\ngraph TD\nA-->B\n```\n后缀"
    result = mermaid.preprocess(md, tmp_path)
    assert "```mermaid" not in result
    assert ".png" in result
    assert "前缀" in result and "后缀" in result


# --- Chrome 自动检测（避免 puppeteer 自带 Chromium 在 Windows 崩溃） ---


def test_find_system_chrome_returns_existing_path(monkeypatch, tmp_path):
    """存在的 Chrome 路径被返回。"""
    fake_chrome = tmp_path / "chrome.exe"
    fake_chrome.write_bytes(b"FAKE")
    monkeypatch.setattr("md2doc.mermaid.sys.platform", "win32")
    monkeypatch.setattr(
        "md2doc.mermaid._CHROME_PATHS",
        {"win32": [str(fake_chrome)], "darwin": []},
    )
    assert mermaid._find_system_chrome() == str(fake_chrome)


def test_find_system_chrome_returns_none_when_not_found(monkeypatch):
    """所有候选路径都不存在时返回 None。"""
    monkeypatch.setattr("md2doc.mermaid.sys.platform", "win32")
    monkeypatch.setattr(
        "md2doc.mermaid._CHROME_PATHS",
        {"win32": ["/nonexistent/chrome.exe"], "darwin": []},
    )
    assert mermaid._find_system_chrome() is None


def test_build_mmdc_env_returns_none_when_nothing_available(monkeypatch):
    """既无环境变量，也未找到系统 Chrome 时返回 None（让 subprocess 用默认环境）。"""
    monkeypatch.delenv("PUPPETEER_EXECUTABLE_PATH", raising=False)
    monkeypatch.setattr("md2doc.mermaid._find_system_chrome", lambda: None)
    assert mermaid._build_mmdc_env() is None


def test_build_mmdc_env_uses_existing_env_var(monkeypatch):
    """用户已设 PUPPETEER_EXECUTABLE_PATH 时优先使用，不调用 Chrome 检测。"""
    monkeypatch.setenv("PUPPETEER_EXECUTABLE_PATH", "/custom/chrome")
    monkeypatch.setattr("md2doc.mermaid._find_system_chrome", lambda: None)
    env = mermaid._build_mmdc_env()
    assert env is not None
    assert env["PUPPETEER_EXECUTABLE_PATH"] == "/custom/chrome"


def test_build_mmdc_env_auto_detects_chrome(monkeypatch):
    """无环境变量但找到系统 Chrome 时，自动设置 env。"""
    monkeypatch.delenv("PUPPETEER_EXECUTABLE_PATH", raising=False)
    monkeypatch.setattr("md2doc.mermaid._find_system_chrome", lambda: "/auto/chrome")
    env = mermaid._build_mmdc_env()
    assert env is not None
    assert env["PUPPETEER_EXECUTABLE_PATH"] == "/auto/chrome"


def test_render_all_passes_chrome_env_to_subprocess(monkeypatch, tmp_path):
    """render_all 把 env 透传给 subprocess.run。"""
    captured_envs = []

    def fake_run(args, **kwargs):
        captured_envs.append(kwargs.get("env"))
        out_idx = args.index("-o")
        Path(args[out_idx + 1]).write_bytes(b"PNG")
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: "/usr/local/bin/mmdc")
    monkeypatch.setattr("md2doc.mermaid.subprocess.run", fake_run)
    monkeypatch.delenv("PUPPETEER_EXECUTABLE_PATH", raising=False)
    monkeypatch.setattr("md2doc.mermaid._find_system_chrome", lambda: "/auto/chrome")

    blocks = [MermaidBlock(id="mermaid_0", code="graph TD", start=0, end=0)]
    mermaid.render_all(blocks, tmp_path)

    assert len(captured_envs) == 1
    assert captured_envs[0] is not None
    assert captured_envs[0]["PUPPETEER_EXECUTABLE_PATH"] == "/auto/chrome"


def test_render_all_env_none_when_no_chrome(monkeypatch, tmp_path):
    """无 Chrome 时 env 为 None，subprocess 继承当前环境。"""
    captured_envs = []

    def fake_run(args, **kwargs):
        captured_envs.append(kwargs.get("env"))
        out_idx = args.index("-o")
        Path(args[out_idx + 1]).write_bytes(b"PNG")
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr("md2doc.mermaid.shutil.which", lambda name: "/usr/local/bin/mmdc")
    monkeypatch.setattr("md2doc.mermaid.subprocess.run", fake_run)
    monkeypatch.delenv("PUPPETEER_EXECUTABLE_PATH", raising=False)
    monkeypatch.setattr("md2doc.mermaid._find_system_chrome", lambda: None)

    blocks = [MermaidBlock(id="mermaid_0", code="graph TD", start=0, end=0)]
    mermaid.render_all(blocks, tmp_path)

    assert captured_envs[0] is None
