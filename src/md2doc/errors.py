"""md2doc 自定义异常层级。

每个异常类带 exit_code 属性，cli 层捕获后用其作为进程退出码。
"""


class Md2docError(Exception):
    """所有 md2doc 自定义异常的基类。"""

    exit_code: int = 4


class InvalidInputError(Md2docError):
    """输入路径不存在、参数组合非法等。"""

    exit_code = 2


class DependencyNotFoundError(Md2docError):
    """外部依赖（pandoc/mmdc）未安装。"""

    exit_code = 3


class PandocNotFoundError(DependencyNotFoundError):
    """pandoc 未安装。"""


class MmdcNotFoundError(DependencyNotFoundError):
    """mmdc（mermaid-cli）未安装。"""


class ConversionError(Md2docError):
    """转换过程中的错误（pandoc 报错、mermaid 渲染失败等）。"""
