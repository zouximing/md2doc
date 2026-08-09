# docx 输出格式化设计规格

**日期**：2026-08-10
**状态**：已批准，待写实施计划
**作者**：Claude（基于与用户的头脑风暴）

---

## 1. 目标与范围

### 1.1 一句话描述

为 md2doc 增加对 docx 输出的统一格式化：定义中文字体/字号/段落的标准，标题自动编号，表格与图片自动加中文 caption（"表 1"、"图 1"）。

### 1.2 背景

当前 converter 调用 pandoc 不带任何样式参数，输出全部走 pandoc 默认。`tests/fixtures/full_test.docx` 是用 pandoc 默认模板生成的一个相对漂亮的样例，但仍存在以下问题：

- 标题编号是源 md 里手写的（"1."、"1.1"），删除一个章节要手动改后续全部编号
- 表格和图片没有任何 caption，读者看到一堆孤立的对象
- 字体/字号/段落格式依赖 pandoc 默认，不可控

### 1.3 范围

**本次包含：**

- 新建 reference.docx 模板，统一定义字体/字号/段落
- 新建 Lua filter，自动给图片和表格加中文 caption 编号
- pandoc.py 增加参数：`reference_doc`、`lua_filter`、`number_sections`
- converter.py 增加标题预处理：剥离 md 源里手写的标题编号（仅在临时 staged.md 中剥离，不动用户源文件），避免与 `--number-sections` 重复
- cli.py 增加一个 `--no-style` 总开关
- 单元测试与集成测试

**本次不包含（YAGNI）：**

- PDF / HTML / EPUB 输出的格式化（reference.docx 只对 docx 生效）
- 自定义 caption 文案模板
- 多级标题样式的 GUI 配置
- "首个 H1 不编号"的特殊处理（用户可在 md 用 YAML title 表达）

---

## 2. 整体架构

### 2.1 模块划分

```
src/md2doc/
├── converter.py        # 改：加标题预处理 + styled 参数
├── pandoc.py           # 改：加 reference_doc / lua_filter / number_sections 参数
├── mermaid.py          # 不动
├── cli.py              # 改：加 --no-style 开关
└── templates/          # 新
    ├── reference.docx  # 新：样式模板
    └── caption.lua     # 新：图片/表格 caption 注入

scripts/
└── build_reference_docx.py  # 新：程序化生成 reference.docx 的脚本

tests/
├── test_pandoc.py            # 新：参数构造单测
├── test_converter.py         # 加：标题剥离正则单测
└── test_integration_styled.py # 新：生成 docx 验证关键样式
```

### 2.2 数据流

```
源 md
   ↓
[mermaid.preprocess]   现状不变
   ↓
[strip_heading_numbers]  新：剥离 "1." "1.1.1" 等手写编号
   ↓
staged.md → 临时文件
   ↓
[pandoc.convert]
   ├─ --reference-doc=templates/reference.docx
   ├─ --lua-filter=templates/caption.lua
   └─ --number-sections
   ↓
最终 .docx
```

---

## 3. 模块详细设计

### 3.1 reference.docx 模板

**生成方式**：用 `scripts/build_reference_docx.py` 程序化生成（python-docx），便于版本控制和 diff，避免手工编辑二进制 docx 文件。

**模板内必须包含的样式定义**：

| 样式名 | 中文 (eastAsia) | 西文 (ascii) | 字号 | 加粗 | 其它 |
|---|---|---|---|---|---|
| Normal | 宋体 | Times New Roman | 12pt | — | 文档默认 |
| Title | 黑体 | — | 18pt | 是 | — |
| Heading 1 | 黑体 | — | 18pt | 是 | outlineLvl=0 |
| Heading 2 | 黑体 | — | 16pt | 是 | outlineLvl=1 |
| Heading 3 | 黑体 | — | 14pt | 是 | outlineLvl=2 |
| Heading 4 | 黑体 | — | 12pt | 是 | outlineLvl=3 |
| Heading 5 | 黑体 | — | 12pt | 是 | outlineLvl=4 |
| Heading 6 | 黑体 | — | 12pt | 是 | outlineLvl=5 |
| Body Text | 宋体 | Times New Roman | 12pt | — | 首行缩进 2 字符, 1.5 倍行距 |
| First Paragraph | 宋体 | Times New Roman | 12pt | — | 首行缩进 2 字符, 1.5 倍行距, 段前 9pt |
| Compact | 宋体 | Times New Roman | 12pt | — | 无缩进, 段前/段后 3pt |
| Block Text | 宋体 | Times New Roman | 10.5pt | — | 段后 10pt |
| Source Code | — | Consolas | 10pt | — | 左缩进 0.5cm, 颜色 #404040 |
| Image Caption | 黑体 | — | 10.5pt | — | **居中** |
| Table Caption | 黑体 | — | 10.5pt | — | **居中** |

**模板复用现有 pandoc 默认样式名**（Heading 1、Body Text、Source Code 等），这样 pandoc 输出的段落自动套用模板样式。新加的 `Image Caption` 和 `Table Caption` 通过 Lua filter 强制应用到对应段落。

**包数据**：通过 pyproject.toml 的 `[tool.setuptools.package-data]` 配置，确保 `md2doc.templates.*` 资源随 pip 安装。

### 3.2 caption.lua

Lua filter 在 pandoc AST 层操作，处理顺序：

```lua
-- 伪代码
local img_count = 0
local tbl_count = 0

function Image(el)
  if el.caption and #el.caption > 0 then
    img_count = img_count + 1
    local prefix = pandoc.Strong({pandoc.Str(string.format("图 %d: ", img_count))})
    -- 把 "图 N: " 插到原 caption 前面
    table.insert(el.caption, 1, prefix)
    table.insert(el.caption, 2, pandoc.Space())
    return el
  end
  -- 无 caption 的 inline image 不编号
end

function Table(el)
  tbl_count = tbl_count + 1
  local cap_text = string.format("表 %d", tbl_count)
  el.caption = pandoc.Plain({pandoc.Str(cap_text)})
  return el
end
```

**关键决策**：

- **Image 编号策略**：pandoc 把带 caption 的 `![xxx](path)` 识别为 Figure（Block 级），inline image（无 caption）不编号。Lua filter 只处理 Figure 形式的 Image。
- **mermaid 图的 caption 来源**：mermaid.py 替换时统一写 `![图](path)`，所以 caption 文本是 "图"。Lua filter 改为 "图 N: 图"。这个语义略冗余但可接受；后续若需要按 mermaid 类型生成 caption（如 "图 N: 流程图"），扩展 mermaid.py 即可，不在本次范围。
- **Table 编号策略**：pandoc 输出的所有 Table 都编号，不管有没有 caption。
- **caption 样式应用**：pandoc 给 Figure caption 默认套 "Image Caption" 样式，给 Table caption 默认套 "Table Caption" 样式。reference.docx 里这两个样式已定义为"居中 + 黑体 10.5pt"。

### 3.3 pandoc.py 修改

`convert()` 签名扩展：

```python
def convert(
    input_path: str | Path,
    output_path: str | Path,
    fmt: str,
    *,
    reference_doc: str | Path | None = None,
    lua_filter: str | Path | None = None,
    number_sections: bool = False,
) -> None:
```

仅 docx 格式时这三个参数才有意义，但不在 pandoc.py 里做格式判断（保持模块纯粹），由调用方 converter.py 决定。

参数构造：

```python
args = [pandoc_path, str(input_path), "-o", str(output_path), "--from=markdown", f"--to={fmt}"]
if reference_doc:
    args.append(f"--reference-doc={reference_doc}")
if lua_filter:
    args.append(f"--lua-filter={lua_filter}")
if number_sections:
    args.append("--number-sections")
```

### 3.4 converter.py 修改

**新增标题预处理函数**：

```python
_HEADING_NUM_PATTERN = re.compile(
    r"^(#{1,6})\s+(?:\d+(?:\.\d+)*)\.?\s+(.+)$",
    re.MULTILINE,
)

def strip_heading_numbers(md: str) -> str:
    """剥离标题里手写的章节编号（"## 1. xxx" → "## xxx"）。

    仅在 staged.md 上执行，不动用户源文件。
    """
    return _HEADING_NUM_PATTERN.sub(r"\1 \2", md)
```

**strip 行为示例**：

| 输入 | 输出 |
|---|---|
| `## 1. 基础文本元素` | `## 基础文本元素` |
| `### 1.1 段落与换行` | `### 段落与换行` |
| `#### 2.1.1.1 四级标题` | `#### 四级标题` |
| `# md2doc 全面测试文档` | `# md2doc 全面测试文档`（无编号不动） |
| `## 1 一些章节` | `## 一些章节`（带不带末尾点都剥） |
| `## 1.2.3. 变长编号` | `## 变长编号` |

**convert_file 改造**：

```python
def convert_file(
    input_file: Path,
    output_file: Path,
    fmt: str,
    no_mermaid: bool = False,
    styled: bool = True,  # 新增
) -> Path:
    md = input_file.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="md2doc_") as tmpdir:
        if no_mermaid:
            processed = md
        else:
            processed = mermaid.preprocess(md, Path(tmpdir))

        if styled:
            processed = strip_heading_numbers(processed)

        staged = Path(tmpdir) / "_staged.md"
        staged.write_text(processed, encoding="utf-8")

        # 构建 pandoc 调用参数
        kwargs = {}
        if styled and fmt == "docx":
            kwargs["reference_doc"] = _template_path("reference.docx")
            kwargs["lua_filter"] = _template_path("caption.lua")
            kwargs["number_sections"] = True

        pandoc.convert(staged, output_file, fmt, **kwargs)

    return Path(output_file)


def _template_path(name: str) -> Path:
    """返回包内 templates 目录下指定文件的路径。"""
    return Path(__file__).parent / "templates" / name
```

**convert_batch 同步加 `styled` 参数**（透传给 convert_file）。

### 3.5 cli.py 修改

新增 `--no-style` 开关：

```python
parser.add_argument(
    "--no-style",
    action="store_true",
    help="不应用 docx 样式（reference.docx + 自动编号 + caption），使用 pandoc 默认输出",
)
```

调用 `convert_file(..., styled=not args.no_style)` 和 `convert_batch(..., styled=not args.no_style)`。

### 3.6 测试

**`tests/test_pandoc.py`**（新）：
- mock subprocess.run，验证 `convert()` 在不同参数下构造的 args 列表正确
- 单测三个开关的组合（reference_doc + lua_filter + number_sections 全开 / 全关 / 部分）

**`tests/test_converter.py`**（已有，加用例）：
- `strip_heading_numbers` 的表格驱动测试，覆盖上面"行为示例"表格的全部行
- `convert_file` 的 styled=True/False 调用分支（mock pandoc.convert，验证传 kwargs 正确）

**`tests/test_integration_styled.py`**（新，可选慢测试）：
- 跳过条件：`shutil.which("pandoc") is None`
- 真实转换 `tests/fixtures/simple.md` 为 docx，用 python-docx 读回，断言：
  - 至少一个 Heading 段落的 eastAsia 字体 = "黑体"
  - 至少一个 Body Text 段落的 eastAsia 字体 = "宋体"
  - 包含 "图 1" 或 "表 1" 字样的 caption 段落

---

## 4. 错误处理

- pandoc / mmdc 未安装：现有错误不变
- reference.docx 或 caption.lua 缺失：开发期错误（不应发生），让 FileNotFoundError 自然抛出
- Lua filter 语法错误：pandoc 会非零退出，由 ConversionError 包装现有逻辑处理

---

## 5. 兼容性

- 默认 `styled=True`，行为有变更：老用户转换同一 md 会得到不同的 docx（多了样式、编号、caption）。这是设计目标。
- `--no-style` 提供逃生通道，回到旧行为。
- 现有 `tests/fixtures/full_test.docx`、`README.docx`、`CLAUDE.docx` **不重新生成**（用户决定）。

---

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| pandoc Lua filter 在低版本不支持 | 项目最低支持 pandoc 2.x（filter 早已支持），README 已说明依赖 |
| Image Caption / Table Caption 样式名与 pandoc 期望的不一致 | 测试中实际生成 docx 验证 caption 段落确实套用了目标样式 |
| 标题剥离正则误伤合法标题（如 "# 1 是个数字"） | 正则要求"数字. 数字"或"数字."模式，`# 1 是个数字` 中 "1" 后面是空格不是点，不匹配 |
| caption.lua 引用 `pandoc.Strong` 等 API 在不同 pandoc 版本签名差异 | 测试用集成测试验证一次实际生效即可 |

---

## 7. 不做的事（明确边界）

- 不修改 `mermaid.py` 的 caption 文案（保持 `![图](path)`）
- 不处理源 md 里 `## 第1章 xxx` 这种中文数字编号
- 不给 PDF / HTML 输出加样式（reference.docx 只对 docx 生效）
- 不重新生成现有 docx 文件
- 不引入 "首个 H1 不编号" 的特殊逻辑
