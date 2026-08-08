import pytest
from pathlib import Path
from click.testing import CliRunner
from md2doc import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_version_shows_md2doc_and_dependency_versions(runner, monkeypatch):
    monkeypatch.setattr("md2doc.cli.__version__", "0.1.0")
    monkeypatch.setattr("md2doc.cli.pandoc.get_version", lambda: "3.1.13")
    monkeypatch.setattr("md2doc.cli.mermaid.get_version", lambda: "10.6.1")
    result = runner.invoke(cli.main, ["--version"])
    assert result.exit_code == 0
    assert "md2doc" in result.output
    assert "0.1.0" in result.output
    assert "3.1.13" in result.output
    assert "10.6.1" in result.output


def test_version_handles_missing_dependencies(runner, monkeypatch):
    monkeypatch.setattr("md2doc.cli.__version__", "0.1.0")
    monkeypatch.setattr("md2doc.cli.pandoc.get_version", lambda: None)
    monkeypatch.setattr("md2doc.cli.mermaid.get_version", lambda: None)
    result = runner.invoke(cli.main, ["--version"])
    assert result.exit_code == 0
    assert "未安装" in result.output


def test_single_file_conversion_success(runner, tmp_path, monkeypatch):
    """单文件转换成功，退出码 0。"""
    src = tmp_path / "in.md"
    src.write_text("# Hello", encoding="utf-8")

    monkeypatch.setattr(
        "md2doc.cli.converter.convert_file",
        lambda inp, outp, fmt, no_mermaid=False: Path(outp).write_bytes(b"DOCX"),
    )

    result = runner.invoke(cli.main, [str(src)])
    assert result.exit_code == 0
    assert (tmp_path / "in.docx").exists()


def test_single_file_with_explicit_output(runner, tmp_path, monkeypatch):
    src = tmp_path / "in.md"
    src.write_text("# Hello", encoding="utf-8")

    monkeypatch.setattr(
        "md2doc.cli.converter.convert_file",
        lambda inp, outp, fmt, no_mermaid=False: Path(outp).write_bytes(b"DOCX"),
    )

    out = tmp_path / "report.docx"
    result = runner.invoke(cli.main, [str(src), "-o", str(out), "-t", "pdf"])
    assert result.exit_code == 0
    assert out.exists()


def test_input_not_exist_returns_exit_code_2(runner, tmp_path):
    result = runner.invoke(cli.main, [str(tmp_path / "nonexistent.md")])
    assert result.exit_code == 2


def test_batch_without_output_returns_exit_code_2(runner, tmp_path):
    base = tmp_path / "docs"
    base.mkdir()
    result = runner.invoke(cli.main, [str(base)])
    assert result.exit_code == 2


def test_pandoc_not_installed_returns_exit_code_3(runner, tmp_path, monkeypatch):
    from md2doc.errors import PandocNotFoundError
    src = tmp_path / "in.md"
    src.write_text("# Hello", encoding="utf-8")

    def fail(*args, **kwargs):
        raise PandocNotFoundError("pandoc 未安装")

    monkeypatch.setattr("md2doc.cli.converter.convert_file", fail)

    result = runner.invoke(cli.main, [str(src)])
    assert result.exit_code == 3


def test_conversion_error_returns_exit_code_4(runner, tmp_path, monkeypatch):
    from md2doc.errors import ConversionError
    src = tmp_path / "in.md"
    src.write_text("# Hello", encoding="utf-8")

    def fail(*args, **kwargs):
        raise ConversionError("pandoc 失败")

    monkeypatch.setattr("md2doc.cli.converter.convert_file", fail)

    result = runner.invoke(cli.main, [str(src)])
    assert result.exit_code == 4


def test_batch_success_continues_on_failure(runner, tmp_path, monkeypatch):
    base = tmp_path / "docs"
    base.mkdir()
    a = base / "a.md"
    a.write_text("# A", encoding="utf-8")
    b = base / "b.md"
    b.write_text("# B", encoding="utf-8")

    out_dir = tmp_path / "build"

    def fake_convert_file(inp, outp, fmt, no_mermaid=False):
        from md2doc.errors import ConversionError
        if inp.name == "b.md":
            raise ConversionError("b 失败")
        Path(outp).write_bytes(b"OK")
        return Path(outp)

    monkeypatch.setattr("md2doc.cli.converter.convert_file", fake_convert_file)

    result = runner.invoke(cli.main, [str(base), "-o", str(out_dir)])
    assert result.exit_code == 4  # 有失败则 4
    assert (out_dir / "a.docx").exists()
    assert "失败" in result.output or "b.md" in result.output


def test_no_input_shows_help_exit_code_2(runner):
    """无任何参数时显示帮助，退出码 2。"""
    result = runner.invoke(cli.main, [])
    assert result.exit_code == 2
