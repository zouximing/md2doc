"""md2doc 业务编排：扫描输入、解析输出路径、调用 pandoc 和 mermaid。

本模块不含与外部工具的直接交互，全部委托给 pandoc.py 和 mermaid.py。
路径解析与批量收集逻辑在此模块内，可纯单元测试。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from md2doc import mermaid, pandoc
from md2doc.errors import InvalidInputError


def scan_md_files(input_path: Path, recursive: bool = True) -> list[Path]:
    """收集输入路径下的所有 .md 文件（大小写不敏感扩展名）。

    Args:
        input_path: 单个文件或目录。
        recursive: 目录输入时是否递归子目录。

    Returns:
        .md 文件路径列表（单文件输入返回单元素列表）。

    Raises:
        FileNotFoundError: input_path 不存在。
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"输入路径不存在：{input_path}")

    if input_path.is_file():
        return [input_path]

    if recursive:
        return sorted(
            p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() == ".md"
        )
    return sorted(
        p
        for p in input_path.iterdir()
        if p.is_file() and p.suffix.lower() == ".md"
    )


def resolve_output_path(
    input_file: Path,
    output: Path | None,
    fmt: str,
    is_batch: bool,
    base_input_dir: Path | None = None,
) -> Path:
    """根据输入文件和 -o 参数，解析出精确的输出文件路径。

    单文件输入（is_batch=False）规则：
        - output 为 None → 输入同目录，同名，扩展名改为 fmt
        - output 是已存在目录 → 输出到该目录，文件名取自输入
        - output 是已存在文件 → 覆盖该文件
        - output 不存在 → 作为新文件路径（父目录必须存在，否则报错）

    批量输入（is_batch=True）规则：
        - output 为 None → 报错（批量必须指定输出目录）
        - output 是已存在文件 → 报错（批量输出必须是目录）
        - output 是已存在目录 → 镜像源目录结构
        - output 不存在 → 自动创建该目录，镜像源目录结构

    Args:
        input_file: 输入 .md 文件路径。
        output: 用户通过 -o 指定的路径，可为 None。
        fmt: 目标格式（如 'docx'）。
        is_batch: 是否批量模式。
        base_input_dir: 批量模式下的输入根目录，用于计算相对路径。

    Returns:
        精确的输出文件路径。
    """
    input_file = Path(input_file)

    if not is_batch:
        return _resolve_single_output(input_file, output, fmt)
    return _resolve_batch_output(input_file, output, fmt, base_input_dir)


def _resolve_single_output(input_file: Path, output: Path | None, fmt: str) -> Path:
    if output is None:
        return input_file.with_suffix(f".{fmt}")

    output = Path(output)
    if output.exists() and output.is_dir():
        return output / input_file.with_suffix(f".{fmt}").name

    # output 不存在或指向文件 → 当作文件路径
    if not output.parent.exists():
        raise InvalidInputError(
            f"输出目录不存在：{output.parent}（请先创建该目录）"
        )
    return output


def _resolve_batch_output(
    input_file: Path, output: Path | None, fmt: str, base_input_dir: Path | None
) -> Path:
    if output is None:
        raise InvalidInputError("批量转换必须指定输出目录（-o）")
    output = Path(output)

    if output.exists() and output.is_file():
        raise InvalidInputError(
            f"批量模式的输出必须是目录，但 {output} 是一个文件"
        )

    # 计算相对路径（用于镜像）
    # 注意：base_input_dir=None 时回退到 input_file.parent，仅适用于 input_file
    # 直接位于根目录的情况；正常调用方（cli.py）应总是传入正确的 base_input_dir
    if base_input_dir is None:
        base_input_dir = input_file.parent
    base_input_dir = Path(base_input_dir)

    try:
        rel = input_file.relative_to(base_input_dir)
    except ValueError:
        raise InvalidInputError(
            f"输入文件 {input_file} 不在基础目录 {base_input_dir} 下"
        ) from None
    rel_output = rel.with_suffix(f".{fmt}")

    # 如果 output 不存在，自动创建
    if not output.exists():
        output.mkdir(parents=True, exist_ok=True)

    final = output / rel_output
    final.parent.mkdir(parents=True, exist_ok=True)
    return final


def convert_file(
    input_file: Path,
    output_file: Path,
    fmt: str,
    no_mermaid: bool = False,
) -> Path:
    """转换单个 .md 文件到目标格式。

    流程：读源 MD -> mermaid 预处理（除非 no_mermaid）-> 写临时 .md -> pandoc 转换 -> 输出。

    Args:
        input_file: 输入 .md 文件路径。
        output_file: 输出文件路径。
        fmt: 目标格式（如 'docx'）。
        no_mermaid: True 则跳过 mermaid 预处理。

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

        # 写入临时 .md 文件交给 pandoc
        staged = Path(tmpdir) / "_staged.md"
        staged.write_text(processed, encoding="utf-8")
        pandoc.convert(staged, output_file, fmt)

    return Path(output_file)


def convert_batch(
    input_files: list[Path],
    output_dir: Path,
    fmt: str,
    base_input_dir: Path,
    no_mermaid: bool = False,
) -> tuple[list[Path], list[tuple[Path, Exception]]]:
    """批量转换多个 .md 文件。

    单个文件失败不阻塞其余文件。输出在 output_dir 下镜像源目录结构。

    Args:
        input_files: 输入 .md 文件路径列表。
        output_dir: 输出根目录。
        fmt: 目标格式。
        base_input_dir: 输入根目录，用于计算相对路径。
        no_mermaid: 是否跳过 mermaid 预处理。

    Returns:
        (成功列表, 失败列表)。
        成功列表：转换成功的输出文件路径列表。
        失败列表：[(输入文件路径, 异常对象), ...]。
    """
    successes: list[Path] = []
    failures: list[tuple[Path, Exception]] = []

    for input_file in input_files:
        try:
            output_file = resolve_output_path(
                input_file, output_dir, fmt,
                is_batch=True, base_input_dir=base_input_dir,
            )
            actual_output = convert_file(
                input_file, output_file, fmt, no_mermaid=no_mermaid
            )
            successes.append(actual_output)
        except Exception as exc:  # noqa: BLE001 - 批量模式需捕获一切以继续
            failures.append((input_file, exc))

    return successes, failures
