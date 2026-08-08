# md2doc

把 Markdown 转换为 Word（.docx）、PDF、HTML、EPUB 等格式，**内置 mermaid 图表支持**（序列图、流程图等）。

## 工作原理

md2doc 在 [pandoc](https://pandoc.org/) 之上封装了一层：
- 调用 pandoc 保证转换质量
- 转换前自动把 mermaid 代码块渲染为 PNG 图片再嵌入文档（pandoc 本身无法渲染 mermaid）

## 安装

### 1. 安装外部依赖

**pandoc（必需）：**
- Windows: `winget install --id JohnMacFarlane.Pandoc`
- macOS: `brew install pandoc`
- Linux: `sudo apt install pandoc`

**mmdc（仅当文档含 mermaid 图时需要）：**

需要先有 Node.js，然后：
- `npm install -g @mermaid-js/mermaid-cli`

### 2. 安装 md2doc

```bash
git clone <repo>
cd md2doc
pip install .
```

## 快速开始

```bash
# 单文件，输出 .docx（默认）
md2doc input.md

# 指定输出路径
md2doc input.md -o report.docx

# 输出 PDF / HTML / EPUB
md2doc input.md -t pdf
md2doc input.md -t html

# 批量转换整个目录
md2doc docs/ -o output/

# 跳过 mermaid 预处理（无图时加速）
md2doc input.md --no-mermaid
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `INPUT` | 输入 .md 文件或目录 |
| `-o, --output PATH` | 输出文件或目录 |
| `-t, --format FORMAT` | 输出格式（默认 docx） |
| `-r, --no-recursive` | 目录输入时不递归子目录 |
| `--no-mermaid` | 跳过 mermaid 预处理 |
| `-V, --version` | 显示版本号与依赖版本 |
| `-h, --help` | 帮助 |

## Mermaid 支持

在 Markdown 中用 ` ```mermaid ` 代码块写图：

    ```mermaid
    sequenceDiagram
        Alice->>Bob: Hello
        Bob-->>Alice: Hi
    ```

md2doc 会自动把所有 mermaid 块渲染为 PNG 并嵌入输出文档。

## 常见问题

**报错"未找到 pandoc"：** 参考上方安装外部依赖部分。

**报错"未找到 mmdc"：** 你的 Markdown 含 mermaid 图，需要额外安装 `npm install -g @mermaid-js/mermaid-cli`。若明知文档无图却报此错，请用 `--no-mermaid` 跳过预处理。

**输出目录会被自动创建吗？** 批量模式（输入是目录）下，`-o` 指向不存在的目录会自动创建。

## Web 界面

md2doc 还提供 Web 界面，支持浏览器上传 / 在线编辑 / 实时预览 / 下载 .docx。

### 启动

```bash
pip install -e ".[web]"        # 安装 FastAPI/uvicorn 等额外依赖
md2doc-web                      # 默认监听 0.0.0.0:8000
# 或自定义：
md2doc-web --host 127.0.0.1 --port 9000
```

打开浏览器访问 `http://localhost:8000`。

### 使用

- **上传 .md**：点击"上传 .md"按钮选择本地 markdown 文件，内容加载到编辑框
- **在线编辑**：在左侧 CodeMirror 编辑器中输入 markdown，右侧预览区约 600ms 后自动更新
- **下载 .docx**：点击"下载 .docx"按钮，浏览器下载转换后的 Word 文档

### 注意事项

- 预览路径**跳过** mermaid 渲染（含 mermaid 的代码块会显示"下载时才会渲染"提示），下载 .docx 时才会调用 mmdc 渲染
- 内网多人共用部署，无认证；公网部署请自行加反向代理 + 认证
- CodeMirror 通过 `esm.sh` CDN 加载，离线内网环境需提前镜像或改本地静态文件
- 文本/文件上限 10MB
