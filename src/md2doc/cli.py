"""md2doc 命令行接口。

参数解析（click）+ 输出格式化（rich）。业务逻辑全部委托给 converter 模块。
"""

from pathlib import Path

import click
from rich.console import Console

from md2doc import __version__, converter, mermaid, pandoc
from md2doc.errors import DependencyNotFoundError, InvalidInputError, Md2docError

_console = Console()


def _print_version():
    _console.print(f"md2doc {__version__}")
    pandoc_ver = pandoc.get_version()
    _console.print(f"pandoc {pandoc_ver or '未安装'}")
    mmdc_ver = mermaid.get_version()
    _console.print(f"mmdc   {mmdc_ver or '未安装'}")


@click.command()
@click.argument("input", type=click.Path(exists=False), required=False)
@click.option("-o", "--output", type=click.Path(exists=False), default=None, help="输出文件或目录")
@click.option("-t", "--format", "fmt", default="docx", help="输出格式（docx/pdf/html/epub/...）")
@click.option("--recursive/--no-recursive", "-r", default=True, help="目录输入时是否递归子目录")
@click.option("--no-mermaid", is_flag=True, default=False, help="跳过 mermaid 预处理")
@click.option("-V", "--version", "show_version", is_flag=True, default=False, help="显示版本号与依赖版本")
def main(input, output, fmt, recursive, no_mermaid, show_version):
    """把 INPUT (.md 文件或目录) 转换为目标格式。"""
    if show_version:
        _print_version()
        return

    if input is None:
        click.echo(main.get_help(click.Context(main)))
        raise SystemExit(2)

    input_path = Path(input)
    if not input_path.exists():
        _console.print(f"[red]✗ 输入路径不存在：{input_path}[/red]")
        raise SystemExit(2)

    is_batch = input_path.is_dir()

    # 批量模式校验
    if is_batch and output is None:
        _console.print("[red]✗ 批量转换必须指定输出目录（-o）[/red]")
        raise SystemExit(2)

    try:
        if not is_batch:
            _convert_single(input_path, output, fmt, no_mermaid)
        else:
            _convert_directory(input_path, output, fmt, recursive, no_mermaid)
    except DependencyNotFoundError as exc:
        _console.print(f"[red]✗ {exc}[/red]")
        raise SystemExit(exc.exit_code)
    except Md2docError as exc:
        _console.print(f"[red]✗ {exc}[/red]")
        raise SystemExit(exc.exit_code)
    except Exception as exc:
        _console.print(f"[red]✗ 未预期的错误：{exc}[/red]")
        raise SystemExit(4)


def _convert_single(input_path, output, fmt, no_mermaid):
    output_file = converter.resolve_output_path(
        input_path, Path(output) if output else None, fmt, is_batch=False
    )
    converter.convert_file(input_path, output_file, fmt, no_mermaid=no_mermaid)
    _console.print(f"[green]✓[/green] {input_path} → {output_file}")


def _convert_directory(input_path, output, fmt, recursive, no_mermaid):
    output_dir = Path(output)
    files = converter.scan_md_files(input_path, recursive=recursive)
    if not files:
        _console.print(f"[yellow]⚠ 目录中没有 .md 文件：{input_path}[/yellow]")
        return

    successes, failures = converter.convert_batch(
        files, output_dir, fmt, base_input_dir=input_path, no_mermaid=no_mermaid
    )
    for s in successes:
        _console.print(f"[green]✓[/green] {s}")
    for f, exc in failures:
        _console.print(f"[red]✗ {f}：{exc}[/red]")

    _console.print(f"已转换 {len(successes)} 个，失败 {len(failures)} 个")
    if failures:
        # 依赖缺失（如 pandoc/mmdc 未装）使用专用退出码 3，其他转换错误用 4
        first_dep_error = next(
            (exc for _, exc in failures if isinstance(exc, DependencyNotFoundError)),
            None,
        )
        if first_dep_error is not None:
            raise SystemExit(first_dep_error.exit_code)
        raise SystemExit(4)


if __name__ == "__main__":
    main()
