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


# --- convert_file ---

def test_convert_file_calls_mermaid_and_pandoc(monkeypatch, tmp_path):
    """验证 convert_file 正确编排：读 -> mermaid.preprocess -> pandoc.convert。"""
    src = tmp_path / "in.md"
    src.write_text("```mermaid\ngraph TD\nA-->B\n```", encoding="utf-8")
    out = tmp_path / "out.docx"

    calls = {"mermaid": False, "pandoc": False}

    def fake_preprocess(md, work_dir):
        calls["mermaid"] = True
        return md  # 原样返回

    def fake_pandoc_convert(input_path, output_path, fmt):
        calls["pandoc"] = True
        Path(output_path).write_bytes(b"DOCX")

    monkeypatch.setattr("md2doc.converter.mermaid.preprocess", fake_preprocess)
    monkeypatch.setattr("md2doc.converter.pandoc.convert", fake_pandoc_convert)

    result = converter.convert_file(src, out, "docx", no_mermaid=False)
    assert result == out
    assert calls["mermaid"] is True
    assert calls["pandoc"] is True


def test_convert_file_skips_mermaid_when_no_mermaid_flag(monkeypatch, tmp_path):
    """--no-mermaid 时不调用 mermaid.preprocess。"""
    src = tmp_path / "in.md"
    src.write_text("# Hello", encoding="utf-8")
    out = tmp_path / "out.docx"

    called = {"mermaid": False}

    def fake_preprocess(md, work_dir):
        called["mermaid"] = True
        return md

    monkeypatch.setattr("md2doc.converter.mermaid.preprocess", fake_preprocess)
    monkeypatch.setattr(
        "md2doc.converter.pandoc.convert",
        lambda *a, **kw: Path(a[1]).write_bytes(b"DOCX"),
    )

    converter.convert_file(src, out, "docx", no_mermaid=True)
    assert called["mermaid"] is False


def test_convert_file_writes_intermediate_md_to_tempdir(monkeypatch, tmp_path):
    """验证预处理后的 MD 写到临时文件，再交给 pandoc（而非原地改源文件）。"""
    src = tmp_path / "in.md"
    original = "```mermaid\ngraph TD\nA-->B\n```"
    src.write_text(original, encoding="utf-8")
    out = tmp_path / "out.docx"

    captured_inputs = []

    def fake_pandoc_convert(input_path, output_path, fmt):
        captured_inputs.append(Path(input_path).read_text(encoding="utf-8"))
        Path(output_path).write_bytes(b"DOCX")

    monkeypatch.setattr(
        "md2doc.converter.mermaid.preprocess",
        lambda md, d: md + "\n[已预处理]",
    )
    monkeypatch.setattr("md2doc.converter.pandoc.convert", fake_pandoc_convert)

    converter.convert_file(src, out, "docx", no_mermaid=False)

    # 源文件未被修改
    assert src.read_text(encoding="utf-8") == original
    # 传给 pandoc 的是预处理后的内容
    assert "[已预处理]" in captured_inputs[0]


# --- convert_batch ---

def test_convert_batch_returns_success_and_failure_lists(monkeypatch, tmp_path):
    """批量转换中某个文件失败不阻塞其余，返回成功/失败列表。"""
    base = tmp_path / "docs"
    base.mkdir()
    a = base / "a.md"
    a.write_text("# A", encoding="utf-8")
    b = base / "b.md"
    b.write_text("# B", encoding="utf-8")
    c = base / "c.md"
    c.write_text("# C", encoding="utf-8")

    out_dir = tmp_path / "build"

    call_count = {"n": 0}

    def fake_convert_file(input_file, output_file, fmt, no_mermaid=False):
        call_count["n"] += 1
        # b.md 转换失败
        if input_file.name == "b.md":
            from md2doc.errors import ConversionError
            raise ConversionError("b.md 失败")
        Path(output_file).write_bytes(b"OK")

    monkeypatch.setattr("md2doc.converter.convert_file", fake_convert_file)

    successes, failures = converter.convert_batch(
        [a, b, c], out_dir, "docx", base_input_dir=base, no_mermaid=False
    )

    assert len(successes) == 2
    assert len(failures) == 1
    assert failures[0][0] == b
    assert call_count["n"] == 3  # 三个都尝试了


def test_convert_batch_mirrors_output_structure(monkeypatch, tmp_path):
    """批量转换保留子目录结构。"""
    base = tmp_path / "docs"
    sub = base / "guide"
    sub.mkdir(parents=True)
    a = base / "a.md"
    a.write_text("# A", encoding="utf-8")
    b = sub / "b.md"
    b.write_text("# B", encoding="utf-8")

    out_dir = tmp_path / "build"

    def fake_convert_file(input_file, output_file, fmt, no_mermaid=False):
        Path(output_file).write_bytes(b"OK")
        return Path(output_file)

    monkeypatch.setattr("md2doc.converter.convert_file", fake_convert_file)

    successes, _ = converter.convert_batch(
        [a, b], out_dir, "docx", base_input_dir=base, no_mermaid=False
    )

    assert out_dir / "a.docx" in successes
    assert out_dir / "guide" / "b.docx" in successes
    assert (out_dir / "guide" / "b.docx").exists()


def test_convert_batch_empty_input_returns_empty_lists(monkeypatch, tmp_path):
    """空输入返回空列表。"""
    out_dir = tmp_path / "build"
    successes, failures = converter.convert_batch(
        [], out_dir, "docx", base_input_dir=tmp_path, no_mermaid=False
    )
    assert successes == []
    assert failures == []
