# md2doc 设计规格

**日期**：2026-08-08
**状态**：已批准，待写实施计划
**作者**：Claude（基于与用户的头脑风暴）

---

## 1. 目标与范围

### 1.1 一句话描述

`md2doc` 是一个命令行工具，把 Markdown 文件转换为 Word（.docx）、PDF、HTML、EPUB 等格式，**内置 mermaid 图表（序列图、流程图等）的渲染支持**。

### 1.2 核心价值

- 调用 pandoc 保证转换质量（pandoc 是文档转换的事实标准）
- 在 pandoc 之前预处理 mermaid 代码块，把图渲染成 PNG 再嵌入，解决 pandoc 无法渲染 mermaid 的痛点
- 提供简洁的命令行体验，支持单文件与批量目录转换

### 1.3 范围

**本次包含：**
- 单文件 / 目录批量转换
- 多种输出格式（pandoc 支持的任意格式，默认 .docx）
- mermaid 图表预处理（序列图、流程图、类图等所有 mermaid 类型）
- 外部依赖检测与友好的错误提示
- 完整测试覆盖

**本次不包含（YAGNI）：**
- 样式定制（字体、页边距、参考模板）—— 使用 pandoc 默认输出
- GUI / Web 界面
- 自定义 pandoc filter 链
- 发布到 PyPI（先做本地可用的工具）

---

## 2. 整体架构

### 2.1 目录结构

```
md2doc/
├── pyproject.toml          # 项目元数据 + 依赖 + 入口点
├── README.md
├── src/
│   └── md2doc/
│       ├── __init__.py
│       ├── __main__.py     # 支持 python -m md2doc
│       ├── cli.py          # click 命令定义、参数解析
│       ├── converter.py    # 核心转换编排（调用 pandoc + mermaid）
│       ├── pandoc.py       # pandoc 检测、版本查询、调用封装
│       ├── mermaid.py      # mermaid 提取、渲染(mmdc)、代码块替换
│       └── errors.py       # 自定义异常
└── tests/
    ├── __init__.py
    ├── test_pandoc.py      # pandoc 检测/调用的测试
    ├── test_mermaid.py     # mermaid 提取/替换/渲染的测试
    ├── test_converter.py   # 转换逻辑测试
    ├── test_cli.py         # CLI 参数解析与退出码测试
    └── fixtures/           # 测试用的 .md 文件
        ├── simple.md
        ├── with_mermaid.md
        ├── multi_mermaid.md
        ├── invalid_mermaid.md
        └── batch/
            ├── a.md
            ├── c.md
            └── sub/
                └── b.md
```

### 2.2 模块职责

| 模块 | 职责 | 不包含 |
|------|------|--------|
| `cli.py` | 解析参数、调用 converter、格式化输出 | 业务逻辑 |
| `converter.py` | 业务编排：扫描输入 → 读 MD → 调 mermaid 预处理 → 调 pandoc → 写输出 | 与外部工具的直接交互 |
| `pandoc.py` | pandoc 的检测、版本查询、调用（**唯一与 pandoc 交互的地方**） | 业务流程 |
| `mermaid.py` | mermaid 的提取、渲染（mmdc）、代码块替换（**唯一与 mmdc 交互的地方**） | 业务流程 |
| `errors.py` | 自定义异常类 | 任何逻辑 |

**关键设计原则：** `pandoc.py` 和 `mermaid.py` 是仅有的两个外部依赖边界，测试时只需 mock 它们，其余逻辑可纯 Python 测试。

### 2.3 转换流程

```
输入(.md 文件/目录)
  ↓
converter.scan_inputs()      # 单文件或递归收集 .md
  ↓
对每个 .md 文件：
  ↓
读取 MD 内容
  ↓
未指定 --no-mermaid？
  ↓ 是
mermaid.has_blocks(md)?
  ├─ 否 ──→ 跳过预处理
  └─ 是
       ↓
       检查 mmdc 是否安装 → 未装 → 抛 MmdcNotFoundError（严格模式，退出码 3）
       ↓ 已装
       mermaid.render_all(blocks) → 渲染 PNG 到临时目录
       mermaid.replace_blocks(md, png_paths) → 替换代码块为 ![](path)
  ↓
pandoc.convert(preprocessed_md, format) → 目标格式
  ↓
写到输出路径
```

---

## 3. 命令行接口

### 3.1 基本用法

```bash
# 最简单：单个文件，输出 .docx（默认）
md2doc input.md

# 指定输出路径
md2doc input.md -o report.docx

# 指定输出格式（pandoc 支持的任意格式）
md2doc input.md -t pdf
md2doc input.md -t html
md2doc input.md -t epub

# 批量转换整个目录（递归）
md2doc docs/ -o output/
md2doc docs/ -t pdf -o output/
```

### 3.2 参数表

| 参数 | 短选项 | 类型 | 默认值 | 说明 |
|------|--------|------|--------|------|
| `input` | - | 路径 | 必填 | 输入 .md 文件或目录 |
| `--output` | `-o` | 路径 | 见 §3.3 | 输出文件或目录 |
| `--format` | `-t` | 字符串 | `docx` | 输出格式（docx/pdf/html/epub/...） |
| `--recursive` | `-r` | 标志 | `True` | 目录输入时递归子目录 |
| `--no-mermaid` | - | 标志 | `False` | 跳过 mermaid 预处理 |
| `--version` | `-V` | - | - | 显示 md2doc/pandoc/mmdc 三者版本 |
| `--help` | `-h` | - | - | 帮助信息 |

### 3.3 输出路径解析规则

**单文件输入：**
- 未指定 `-o` → 输出到输入文件同目录，同名，扩展名改为目标格式（`input.md` → `input.docx`）
- `-o` 路径存在且是目录 → 输出到该目录，文件名取自输入
- `-o` 路径存在且是文件 → 覆盖该文件（用户明确指定即视为同意）
- `-o` 路径不存在 → 作为输出文件路径创建（父目录必须存在，否则报错）

**目录输入（批量）：**
- 未指定 `-o` → **报错**（批量模式必须明确输出目录，避免污染源目录）
- `-o` 路径存在且是文件 → **报错**（批量模式输出必须是目录）
- `-o` 路径存在且是目录 → 在输出目录下**镜像**源目录结构（保留子目录层级）
- `-o` 路径不存在 → **自动创建该目录**，然后镜像源目录结构

### 3.4 批量转换的目录镜像

```
输入：                          输出（-o build/）：
docs/                           build/
├── intro.md                    ├── intro.docx
├── guide/                      ├── guide/
│   ├── setup.md         →      │   ├── setup.docx
│   └── usage.md                │   └── usage.docx
└── faq.md                      └── faq.docx
```

输出扩展名由 `--format` 决定（`docx`/`pdf`/`html`/`epub` 等）。

### 3.5 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 2 | 输入/参数错误（路径不存在、批量未指定 `-o` 等） |
| 3 | 外部依赖缺失（pandoc 或 mmdc 未安装） |
| 4 | 转换过程出错（pandoc 报错、mermaid 渲染失败等） |

### 3.6 批量失败处理

批量转换中某个文件失败时，**继续处理其余文件**，最后汇总失败列表，退出码 4。
单文件模式失败则立即退出。

### 3.7 输出风格（使用 rich）

- **成功**：绿色 ✓ `input.md → output.docx`
- **进度**（批量）：每个文件一行
- **警告**：黄色 ⚠
- **错误**：红色 ✗ + 详细信息
- **汇总**（批量）：`已转换 12 个，失败 1 个`

---

## 4. Mermaid 预处理

### 4.1 代码块识别

使用正则匹配 fenced code block，大小写不敏感，容忍 tilde 围栏：

```python
PATTERN = re.compile(
    r'^(?P<fence>```|~~~)\s*mermaid[ \t]*\n'
    r'(?P<code>.*?)'
    r'^(?P=fence)[ \t]*$',
    re.MULTILINE | re.DOTALL | re.IGNORECASE
)
```

提取后得到 `[(match_span, mermaid_code), ...]`。

### 4.2 渲染流程

1. 为每个 mermaid 块生成唯一 ID（`mermaid_0`、`mermaid_1`、...）
2. 写入临时目录：`{tempdir}/mermaid_{id}.mmd`
3. 调用 mmdc：
   ```bash
   mmdc -i mermaid_0.mmd -o mermaid_0.png --scale 2
   ```
   - `--scale 2`：提高分辨率，.docx 中显示更清晰
4. 把原 MD 中的 mermaid 代码块整体替换为：
   ```markdown
   ![图](mermaid_0.png)
   ```

### 4.3 关键决策

**PNG 而非 SVG：**
- .docx 对 SVG 支持差（Word 渲染时可能丢失或不显示）
- PDF 输出经 LaTeX，SVG 需要 rsvg-convert 等额外依赖
- PNG 2x 缩放在 .docx 中清晰度足够，跨格式兼容性最好

**临时目录管理：**
- 使用 `tempfile.TemporaryDirectory()` 作为 context manager
- 渲染的 PNG 和中间 .mmd 文件都在此目录
- **图片路径用绝对路径**写进 MD，避免 pandoc 的工作目录问题
- 转换完成后临时目录自动清理

**空图/无效 mermaid 代码：**
- mmdc 以非零退出码返回，stderr 含错误信息
- converter 捕获后抛 `ConversionError`，错误信息包含：哪个文件、第几个 mermaid 块、mmdc 的原始报错
- 单文件模式：直接退出；批量模式：记录失败，继续下一个文件

### 4.4 接口设计（mermaid.py）

```python
@dataclass
class MermaidBlock:
    id: str              # "mermaid_0"
    code: str            # mermaid 源码
    start: int           # 在原 md 中的起始位置
    end: int             # 在原 md 中的结束位置
    image_path: Path | None  # 渲染后填充

def has_mermaid(md: str) -> bool: ...
def extract_blocks(md: str) -> list[MermaidBlock]: ...
def render_all(blocks: list[MermaidBlock], out_dir: Path) -> list[Path]: ...
def replace_blocks(md: str, blocks: list[MermaidBlock], image_paths: list[Path]) -> str: ...

# 高层封装，供 converter 调用
def preprocess(md: str, work_dir: Path) -> str:
    """如果无 mermaid，返回原 md；否则执行完整预处理流程。"""
```

---

## 5. 错误处理

### 5.1 自定义异常（errors.py）

```python
class Md2docError(Exception):
    """所有自定义异常的基类。"""
    exit_code: int = 4

class InvalidInputError(Md2docError):
    """输入路径不存在、参数组合非法等。"""
    exit_code = 2

class DependencyNotFoundError(Md2docError):
    """外部依赖（pandoc/mmdc）未安装。"""
    exit_code = 3

class PandocNotFoundError(DependencyNotFoundError): ...
class MmdcNotFoundError(DependencyNotFoundError): ...

class ConversionError(Md2docError):
    """转换过程中的错误（pandoc 报错、mermaid 渲染失败等）。"""
    exit_code = 4
```

每个异常类带 `exit_code` 属性，cli 层捕获后直接用其作为进程退出码。

### 5.2 错误信息规范

所有错误信息：
- 第一行简述问题
- 后续行给出**具体的修复建议**（如安装命令）
- 多语言无关，但本项目统一用中文（依用户偏好）

---

## 6. 测试策略

### 6.1 分层测试

**第 1 层：纯逻辑测试（无外部依赖，必跑）**

| 测试文件 | 覆盖内容 |
|----------|----------|
| `test_mermaid.py` | `has_mermaid` 对各种输入（有/无/混合/tilde 围栏/大小写）<br>`extract_blocks` 提取多个块、嵌套代码块不误匹配<br>`replace_blocks` 替换后字符串正确、无残留 |
| `test_converter.py` | 输出路径解析规则（所有分支）<br>目录镜像逻辑<br>批量收集 .md 的递归逻辑 |
| `test_cli.py` | 参数解析（各种组合）<br>退出码（2/3/4） |

**第 2 层：外部工具 mock 测试**

| 测试文件 | 做法 |
|----------|------|
| `test_pandoc.py` | mock `subprocess.run`，验证：调用 pandoc 时的参数构造正确、版本检测、未安装时抛 `PandocNotFoundError` |
| `test_mermaid.py`（渲染部分） | mock `subprocess.run`，验证：mmdc 调用参数（`-i`、`-o`、`--scale 2`）、未安装时抛 `MmdcNotFoundError`、渲染失败时抛 `ConversionError` |

**第 3 层：端到端集成测试（标记 `@pytest.mark.integration`，CI 默认跳过）**

- 准备真实 `fixtures/with_mermaid.md`
- 真实调用 pandoc + mmdc 生成 `fixtures/with_mermaid.docx`
- 断言输出文件存在、非空、文件类型为 zip（.docx 本质）

### 6.2 测试夹具

```
tests/fixtures/
├── simple.md              # 纯文本，无 mermaid
├── with_mermaid.md        # 含一个序列图
├── multi_mermaid.md       # 含多个 mermaid 块 + 普通代码块
├── invalid_mermaid.md     # 含语法错误的 mermaid（用于测错误处理）
└── batch/
    ├── a.md
    ├── c.md
    └── sub/
        └── b.md
```

### 6.3 覆盖目标

- 核心逻辑（不含外部调用）≥ 90%
- 外部调用部分通过 mock 覆盖关键分支
- 不追求 100%（集成测试涉及真实 pandoc，不在常规覆盖率目标内）

---

## 7. 依赖与分发

### 7.1 Python 依赖

**运行时（仅 2 个）：**
- `click>=8.1` — CLI 框架
- `rich>=13.0` — 彩色输出、进度

**开发依赖（可选 extra）：**
- `pytest>=8.0`
- `pytest-cov` — 覆盖率
- `ruff` — lint + format

### 7.2 外部依赖

| 工具 | 必需性 | 安装命令 |
|------|--------|----------|
| `pandoc` | 必需（所有转换都依赖） | Windows: `winget install --id JohnMacFarlane.Pandoc`<br>macOS: `brew install pandoc`<br>Linux: `sudo apt install pandoc` |
| `mmdc`（mermaid-cli） | 按需（仅当 MD 含 mermaid 块） | `npm install -g @mermaid-js/mermaid-cli` |

**延迟检测：** mmdc 只在"检测到 MD 含 mermaid 且未指定 `--no-mermaid`"时才检查，避免无图文档白白报错。

### 7.3 打包

使用现代标准：`pyproject.toml` + `pip install .`，不再用 `setup.py` / `setup.cfg`。

```toml
[project]
name = "md2doc"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = [
    "click>=8.1",
    "rich>=13.0",
]

[project.scripts]
md2doc = "md2doc.cli:main"

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov", "ruff"]
```

`[project.scripts]` 自动注册 `md2doc` 命令到 PATH。

### 7.4 安装方式

```bash
# 方式 1：从源码安装
git clone <repo>
cd md2doc
pip install .

# 方式 2：开发模式
pip install -e ".[dev]"
```

### 7.5 `--version` 行为

一次性打印三件事：

```
md2doc 0.1.0
pandoc 3.1.13    (/usr/bin/pandoc)
mmdc   10.6.1    (/usr/local/bin/mmdc)   [未安装时显示: 未安装]
```

---

## 8. 设计原则小结

1. **外部依赖集中边界化** — pandoc.py 和 mermaid.py 是唯二的外部交互点，其余模块纯逻辑
2. **延迟检测** — mmdc 只在真正需要时才检查，减少无谓错误
3. **YAGNI** — 不做样式定制、GUI、PyPI 发布；pandoc 默认输出就够用
4. **失败不阻塞批量** — 单文件失败不影响其余文件，但最终以退出码 4 提示
5. **PNG 优先** — 跨格式（docx/pdf/html/epub）兼容性最好

---

## 9. 后续步骤

1. 用户审查本设计文档
2. 调用 `writing-plans` skill 生成详细实施计划
3. 按计划实施（TDD）
