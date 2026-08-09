import subprocess

import pytest

from md2doc import pandoc
from md2doc.errors import ConversionError, PandocNotFoundError

# --- 检测 ---

def test_ensure_pandoc_returns_path_when_installed(monkeypatch):
    monkeypatch.setattr("md2doc.pandoc.shutil.which", lambda name: "/usr/bin/pandoc")
    assert pandoc.ensure_pandoc() == "/usr/bin/pandoc"


def test_ensure_pandoc_raises_when_not_installed(monkeypatch):
    monkeypatch.setattr("md2doc.pandoc.shutil.which", lambda name: None)
    with pytest.raises(PandocNotFoundError) as exc_info:
        pandoc.ensure_pandoc()
    msg = str(exc_info.value)
    assert "pandoc" in msg
    assert "安装" in msg  # 错误信息含安装提示


def test_ensure_pandoc_error_message_contains_platform_hints(monkeypatch):
    monkeypatch.setattr("md2doc.pandoc.shutil.which", lambda name: None)
    with pytest.raises(PandocNotFoundError) as exc_info:
        pandoc.ensure_pandoc()
    msg = str(exc_info.value)
    assert "winget" in msg  # Windows
    assert "brew" in msg    # macOS
    assert "apt" in msg     # Linux


# --- 版本查询 ---

def test_get_version_returns_normalized_version(monkeypatch):
    monkeypatch.setattr("md2doc.pandoc.shutil.which", lambda name: "/usr/bin/pandoc")
    monkeypatch.setattr(
        "md2doc.pandoc.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="pandoc 3.1.13\n", stderr=""
        ),
    )
    assert pandoc.get_version() == "3.1.13"


def test_get_version_when_not_installed_returns_none(monkeypatch):
    monkeypatch.setattr("md2doc.pandoc.shutil.which", lambda name: None)
    assert pandoc.get_version() is None


def test_get_version_returns_none_when_output_unparseable(monkeypatch):
    """pandoc 已装但 --version 输出无法匹配正则时返回 None。"""
    monkeypatch.setattr("md2doc.pandoc.shutil.which", lambda name: "/usr/bin/pandoc")
    monkeypatch.setattr(
        "md2doc.pandoc.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="完全不含版本号的异常输出\n", stderr=""
        ),
    )
    assert pandoc.get_version() is None


# --- 转换 ---

def test_convert_constructs_correct_command(monkeypatch, tmp_path):
    """验证 convert 调用 pandoc 时的参数构造正确。"""
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("md2doc.pandoc.shutil.which", lambda name: "/usr/bin/pandoc")
    monkeypatch.setattr("md2doc.pandoc.subprocess.run", fake_run)

    input_md = tmp_path / "in.md"
    input_md.write_text("# Hello", encoding="utf-8")
    output_docx = tmp_path / "out.docx"

    pandoc.convert(input_md, output_docx, "docx")

    assert captured["args"][0] == "/usr/bin/pandoc"
    assert str(input_md) in captured["args"]
    assert "-o" in captured["args"]
    assert str(output_docx) in captured["args"]
    assert "--from=markdown" in captured["args"]
    assert "--to=docx" in captured["args"]


def test_convert_raises_on_pandoc_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("md2doc.pandoc.shutil.which", lambda name: "/usr/bin/pandoc")
    monkeypatch.setattr(
        "md2doc.pandoc.subprocess.run",
        lambda args, **kwargs: subprocess.CompletedProcess(
            args=args, returncode=1, stdout="", stderr="pandoc: error: bad input"
        ),
    )
    input_md = tmp_path / "in.md"
    input_md.write_text("# Hello", encoding="utf-8")
    output_docx = tmp_path / "out.docx"

    with pytest.raises(ConversionError) as exc_info:
        pandoc.convert(input_md, output_docx, "docx")
    assert "bad input" in str(exc_info.value)


def test_convert_raises_when_pandoc_not_installed(monkeypatch, tmp_path):
    monkeypatch.setattr("md2doc.pandoc.shutil.which", lambda name: None)
    input_md = tmp_path / "in.md"
    input_md.write_text("# Hello", encoding="utf-8")
    with pytest.raises(PandocNotFoundError):
        pandoc.convert(input_md, tmp_path / "out.docx", "docx")


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
