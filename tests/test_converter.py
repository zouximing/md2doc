import pytest
from pathlib import Path
from md2doc import converter


# --- scan_md_files ---

def test_scan_single_file_returns_singleton_list(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("# A", encoding="utf-8")
    result = converter.scan_md_files(f, recursive=True)
    assert result == [f]


def test_scan_single_file_raises_if_not_exists(tmp_path):
    with pytest.raises(FileNotFoundError):
        converter.scan_md_files(tmp_path / "nonexistent.md", recursive=True)


def test_scan_directory_collects_all_md(tmp_path):
    (tmp_path / "a.md").write_text("# A", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B", encoding="utf-8")
    (tmp_path / "readme.txt").write_text("ignore", encoding="utf-8")
    result = sorted(converter.scan_md_files(tmp_path, recursive=True))
    assert result == [tmp_path / "a.md", tmp_path / "b.md"]


def test_scan_directory_recursive_includes_subdirs(tmp_path):
    (tmp_path / "a.md").write_text("# A", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.md").write_text("# B", encoding="utf-8")
    result = sorted(converter.scan_md_files(tmp_path, recursive=True))
    assert result == [tmp_path / "a.md", sub / "b.md"]


def test_scan_directory_non_recursive_excludes_subdirs(tmp_path):
    (tmp_path / "a.md").write_text("# A", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.md").write_text("# B", encoding="utf-8")
    result = sorted(converter.scan_md_files(tmp_path, recursive=False))
    assert result == [tmp_path / "a.md"]


def test_scan_is_case_insensitive_for_extension(tmp_path):
    f = tmp_path / "README.MD"
    f.write_text("# A", encoding="utf-8")
    result = converter.scan_md_files(tmp_path, recursive=True)
    assert f in result


# --- resolve_output_path（单文件输入） ---

def test_single_file_default_output_same_dir(tmp_path):
    """未指定 -o，输出到同目录，扩展名改为目标格式。"""
    src = tmp_path / "input.md"
    result = converter.resolve_output_path(src, None, "docx", is_batch=False)
    assert result == tmp_path / "input.docx"


def test_single_file_output_to_existing_dir(tmp_path):
    """-o 是已存在的目录，输出到该目录。"""
    src = tmp_path / "input.md"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = converter.resolve_output_path(src, out_dir, "pdf", is_batch=False)
    assert result == out_dir / "input.pdf"


def test_single_file_output_to_explicit_file(tmp_path):
    """-o 是已存在的文件，覆盖。"""
    src = tmp_path / "input.md"
    out_file = tmp_path / "report.docx"
    out_file.write_text("old", encoding="utf-8")
    result = converter.resolve_output_path(src, out_file, "docx", is_batch=False)
    assert result == out_file


def test_single_file_output_to_nonexistent_path(tmp_path):
    """-o 不存在，作为新文件路径创建。"""
    src = tmp_path / "input.md"
    out_file = tmp_path / "report.docx"
    result = converter.resolve_output_path(src, out_file, "docx", is_batch=False)
    assert result == out_file


def test_single_file_output_nonexistent_parent_raises(tmp_path):
    """-o 不存在且父目录也不存在，报错。"""
    from md2doc.errors import InvalidInputError
    src = tmp_path / "input.md"
    out_file = tmp_path / "nonexistent_subdir" / "report.docx"
    with pytest.raises(InvalidInputError):
        converter.resolve_output_path(src, out_file, "docx", is_batch=False)


# --- resolve_output_path（批量输入） ---

def test_batch_no_output_raises(tmp_path):
    from md2doc.errors import InvalidInputError
    src = tmp_path / "a.md"
    src.write_text("# A", encoding="utf-8")
    with pytest.raises(InvalidInputError):
        converter.resolve_output_path(
            src, None, "docx", is_batch=True, base_input_dir=tmp_path
        )


def test_batch_output_is_existing_file_raises(tmp_path):
    from md2doc.errors import InvalidInputError
    src = tmp_path / "a.md"
    src.write_text("# A", encoding="utf-8")
    out_file = tmp_path / "out.docx"
    out_file.write_text("old", encoding="utf-8")
    with pytest.raises(InvalidInputError):
        converter.resolve_output_path(
            src, out_file, "docx", is_batch=True, base_input_dir=tmp_path
        )


def test_batch_output_existing_dir_mirrors_structure(tmp_path):
    base = tmp_path / "docs"
    base.mkdir()
    sub = base / "guide"
    sub.mkdir()
    src = sub / "setup.md"
    src.write_text("# Setup", encoding="utf-8")

    out_dir = tmp_path / "build"
    out_dir.mkdir()

    result = converter.resolve_output_path(
        src, out_dir, "docx", is_batch=True, base_input_dir=base
    )
    assert result == out_dir / "guide" / "setup.docx"


def test_batch_output_nonexistent_dir_is_created(tmp_path):
    base = tmp_path / "docs"
    base.mkdir()
    src = base / "a.md"
    src.write_text("# A", encoding="utf-8")

    out_dir = tmp_path / "new_build"  # 不存在
    result = converter.resolve_output_path(
        src, out_dir, "docx", is_batch=True, base_input_dir=base
    )
    assert result == out_dir / "a.docx"
    # 确保目录被创建
    assert result.parent.exists()


def test_batch_input_file_outside_base_dir_raises(tmp_path):
    """input_file 不在 base_input_dir 下时抛 InvalidInputError（而非原始 ValueError）。"""
    from md2doc.errors import InvalidInputError
    base = tmp_path / "docs"
    base.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    src = outside / "a.md"
    src.write_text("# A", encoding="utf-8")

    out_dir = tmp_path / "build"
    out_dir.mkdir()
    with pytest.raises(InvalidInputError):
        converter.resolve_output_path(
            src, out_dir, "docx", is_batch=True, base_input_dir=base
        )
