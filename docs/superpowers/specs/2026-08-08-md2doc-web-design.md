# md2doc-web 设计

为 md2doc 增加 Web 界面：浏览器上传 .md 或在线编辑 + 实时预览，下载 .docx。

## 1. 目标与非目标

**目标：**
- 单页 Web 应用：上传 .md → 编辑框 → 实时预览 → 下载 .docx（统一流程）
- 内网多人共用，无认证
- 复用现有 `md2doc.converter` 业务逻辑，不改动 CLI

**非目标（YAGNI）：**
- 不做认证、用户系统、持久化、历史记录
- 不做客户端 markdown 渲染（marked.js）
- 不做 PDF/HTML/EPUB 下载
- 不做并发限流、队列
- 不做前端构建工具链（webpack/vite），CodeMirror 走 ESM CDN

## 2. 使用场景

内网部署在一台服务器，团队成员浏览器访问。每个人独立操作，互不干扰。每次请求独立临时目录，互不污染。

## 3. 技术栈

- **后端**：FastAPI + uvicorn（ASGI），`asyncio.run_in_executor` 包裹同步 pandoc/mmdc 调用
- **请求模型**：Pydantic v2
- **文件上传**：`python-multipart`
- **前端**：原生 HTML + ESM JS；CodeMirror 6 via ESM CDN（`esm.sh`）；无构建工具
- **复用**：`md2doc.converter.convert_file`、`md2doc.pandoc.convert`、`md2doc.pandoc.ensure_pandoc`、`md2doc.pandoc.get_version`、`md2doc.mermaid` 模块

## 4. 模块与文件结构

新增 `src/md2doc/web/` 子包，与 `cli.py` 平级。不改动 `src/md2doc/` 现有模块。

```
src/md2doc/
├── (现有模块: __init__.py / __main__.py / cli.py / converter.py /
│              pandoc.py / mermaid.py / errors.py — 不动)
└── web/
    ├── __init__.py          # 空，包标记
    ├── app.py               # FastAPI 应用 + 路由
    ├── dependencies.py      # 依赖注入与错误码常量
    ├── schemas.py           # Pydantic 请求/响应模型
    └── static/
        ├── index.html       # 单页
        ├── app.js           # 前端逻辑
        └── styles.css       # 样式
```

**入口点**：在 `pyproject.toml` 增加：
```toml
[project.scripts]
md2doc = "md2doc.cli:main"
md2doc-web = "md2doc.web.app:main"   # 新增

[project.optional-dependencies]
web = ["fastapi>=0.110", "uvicorn[standard]>=0.27", "python-multipart>=0.0.9"]
```

`md2doc-web` 命令等价于 `uvicorn md2doc.web.app:app --host 0.0.0.0 --port 8000`，并支持 `--host/--port/--reload` 参数透传。Web 功能依赖作为可选 extra，不强制所有用户安装。

## 5. API 设计

所有端点无认证。请求体上限 10MB（FastAPI `Request.body_size_limit` 或读取时校验）。

### 5.1 `GET /`
- 响应：单页 HTML（`FileResponse` 返回 `static/index.html`，200）

### 5.2 `POST /api/upload`
读取上传的 .md 文件文本内容，不转换。

- 请求：`multipart/form-data`，字段 `file`（单个文件，扩展名 `.md`/`.MD`）
- 响应 200：`{"text": "...", "filename": "xxx.md"}`（`UploadResponse`）
- 错误：
  - 415 `UNSUPPORTED_TYPE` — 扩展名非 .md
  - 413 `FILE_TOO_LARGE` — 文件大小 > 10MB
  - 400 `INVALID_INPUT` — 读取失败（编码错误等）

### 5.3 `POST /api/preview`
跳过 mermaid，用 pandoc 把 markdown 转为 HTML 片段返回。

- 请求：`{"text": "...markdown..."}`（`PreviewRequest`）
- 响应 200：`{"html": "...pandoc 输出..."}`（`PreviewResponse`）
- 错误：
  - 500 `DEPENDENCY_MISSING` — pandoc 未安装
  - 500 `CONVERSION_FAILED` — pandoc 执行失败
  - 500 `INTERNAL` — 其他未预期异常

**实现**：
```python
async def preview(req: PreviewRequest):
    text = req.text
    if len(text.encode("utf-8")) > 10 * 1024 * 1024:
        raise WebError("FILE_TOO_LARGE", "文本超过 10MB", 413)
    def run():
        with tempfile.TemporaryDirectory(prefix="md2doc_preview_") as d:
            staged = Path(d) / "_staged.md"
            staged.write_text(text, encoding="utf-8")
            out = Path(d) / "_preview.html"
            pandoc.convert(staged, out, "html")  # 复用现有
            return out.read_text(encoding="utf-8")
    try:
        html = await asyncio.get_event_loop().run_in_executor(None, run)
    except DependencyNotFoundError as e:
        raise WebError("DEPENDENCY_MISSING", str(e), 500)
    except ConversionError as e:
        raise WebError("CONVERSION_FAILED", str(e), 500)
    except Exception as e:
        raise WebError("INTERNAL", f"未预期错误：{e}", 500)
    return PreviewResponse(html=html)
```

注意：预览路径**不**调用 `mermaid.preprocess`，含 mermaid 的代码块以普通 `<pre><code class="language-mermaid">` 出现，前端识别后加提示。

### 5.4 `POST /api/convert`
走完整流程（含 mermaid 渲染），返回 .docx 文件下载。

- 请求：`{"text": "...", "filename": "可选"}`（`ConvertRequest`）
- 响应 200：`application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - `Content-Disposition: attachment; filename="<safe>.docx"`
  - body 是 docx 字节流（`StreamingResponse` 或 `Response(content=bytes)`）
- 错误：同 `/api/preview`

**实现**：
```python
async def convert(req: ConvertRequest):
    text = req.text
    # ... size check 同上
    def run():
        with tempfile.TemporaryDirectory(prefix="md2doc_convert_") as d:
            inp = Path(d) / "_input.md"
            inp.write_text(text, encoding="utf-8")
            out = Path(d) / "_output.docx"
            converter.convert_file(inp, out, "docx", no_mermaid=False)  # 复用
            return out.read_bytes()
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, run)
    except DependencyNotFoundError as e:
        raise WebError("DEPENDENCY_MISSING", str(e), 500)
    except ConversionError as e:
        raise WebError("CONVERSION_FAILED", str(e), 500)
    except Exception as e:
        raise WebError("INTERNAL", f"未预期错误：{e}", 500)
    safe_name = sanitize_filename(req.filename) or "document"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.docx"'},
    )
```

### 5.5 统一错误响应
```json
{"detail": "人类可读信息", "code": "ERROR_CODE"}
```

`WebError` 自定义异常（在 `dependencies.py`），由 FastAPI `exception_handler` 转换为对应 JSON 响应。错误码常量：`INVALID_INPUT`、`FILE_TOO_LARGE`、`UNSUPPORTED_TYPE`、`DEPENDENCY_MISSING`、`CONVERSION_FAILED`、`INTERNAL`。

### 5.6 文件名清理
`sanitize_filename(name)`：取主名（去扩展名）、移除路径分隔符与特殊字符、限定长度（≤80 字符）。空或无效时返回 None（调用方回退到 `"document"`）。

## 6. 前端单页

`static/index.html` + `app.js` + `styles.css`。

### 6.1 布局
```
┌─────────────────────────────────────────────┐
│ [上传.md] [文件名标签]      [下载 .docx]    │ 顶部工具栏
├─────────────────────┬───────────────────────┤
│                     │                       │
│   CodeMirror 6      │   预览区 (div)         │
│   (markdown 编辑)    │   (pandoc 渲染 HTML)  │
│                     │                       │
└─────────────────────┴───────────────────────┘
```

### 6.2 CodeMirror 6 加载
通过 ESM CDN，`app.js` 顶部：
```js
import { EditorState } from "https://esm.sh/codemirror@6.65.7";
import { EditorView, keymap } from "https://esm.sh/@codemirror/view@6.65.7";
import { defaultKeymap } from "https://esm.sh/@codemirror/commands@6.2.2";
import { markdown } from "https://esm.sh/@codemirror/lang-markdown@6.1.0";
```

固定版本号（不跟踪 latest）以保证构建可复现。

### 6.3 行为
- **首次进入**：编辑器预填示例 markdown（`# Hello\n\n这是一段**测试**文本。\n\n- 项目一\n- 项目二`），触发首次预览
- **编辑**：`EditorView.updateListener` 监听 `docChanged` → 防抖 600ms → POST `/api/preview` → 更新 `#preview` 的 `innerHTML`；同时记录递增的 `requestId`，响应返回时若 `id` 已过期则忽略
- **加载中**：预览区右上角小 loading 圆点（CSS class 切换），不阻塞编辑
- **上传**：`<input type="file" accept=".md,.MD" hidden>` + 自定义按钮触发；选文件后 `FormData` POST `/api/upload`，成功则 `editor.dispatch({ effects: EditorView.reconfigure.of(...) })` 替换文档内容为返回的 text；同步更新顶部"文件名标签"；触发一次预览
- **下载**：点击"下载 .docx"按钮 → POST `/api/convert`，请求体含当前编辑器文本与文件名标签 → 拿到 `Blob` → `URL.createObjectURL` + 隐藏 `<a download>` 触发下载；下载中按钮置灰显示"生成中..."
- **错误处理**：所有 fetch 失败（网络错或非 2xx）解析 JSON 后在工具栏下方显示 toast，3 秒后自动消失

### 6.4 mermaid 提示
预览区更新后，`querySelectorAll('code.language-mermaid, pre code.mermaid')` 找到所有 mermaid 代码块，在其 `<pre>` 外层 wrapper 顶部插入一个 `<div class="mermaid-hint">下载 .docx 时此图会被渲染</div>`。纯 DOM 操作，不增加后端负担。

### 6.5 样式
- 全宽自适应布局，最小宽度 800px（更小则纵向堆叠）
- 工具栏：浅灰背景、固定高度
- 编辑器/预览：左右各 50%，可滚动
- 预览区使用系统字体 + 合理的 `max-width` 与行高，让 pandoc 输出的 HTML 可读

## 7. 错误处理

| 场景 | HTTP | code | detail 示例 |
|------|------|------|------------|
| 上传非 .md | 415 | UNSUPPORTED_TYPE | 仅支持 .md 文件 |
| 上传 > 10MB | 413 | FILE_TOO_LARGE | 文件超过 10MB |
| 上传读取失败 | 400 | INVALID_INPUT | 文件读取失败：<原因> |
| 预览/下载 pandoc 未装 | 500 | DEPENDENCY_MISSING | 未找到 pandoc... |
| 预览/下载 pandoc 失败 | 500 | CONVERSION_FAILED | pandoc 转换失败：<原因> |
| 含 mermaid 但 mmdc 未装（仅下载路径） | 500 | DEPENDENCY_MISSING | 未找到 mmdc... |
| 其他未预期异常 | 500 | INTERNAL | 未预期错误：<原因> |

前端按 `code` 区分提示文案：`DEPENDENCY_MISSING` → 红色 toast 提示"服务依赖未安装，请联系管理员"；其他 → 显示 `detail`。

## 8. 测试策略

### 8.1 后端单元测试（pytest + httpx `TestClient`）
- `GET /` 返回 200 且 `text/html` 含 `<div id="editor">`
- `POST /api/upload` 成功返回 text + filename
- `POST /api/upload` .txt → 415
- `POST /api/upload` 超大 → 413（mock 大文件）
- `POST /api/upload` 读取失败 → 400（mock `read_text` 抛异常）
- `POST /api/preview` 成功返回 html，**monkeypatch 断言不调用** `mermaid.preprocess`
- `POST /api/preview` monkeypatch `pandoc.convert` 抛 `DependencyNotFoundError` → 500 + `DEPENDENCY_MISSING`
- `POST /api/preview` monkeypatch `pandoc.convert` 抛 `ConversionError` → 500 + `CONVERSION_FAILED`
- `POST /api/convert` 成功返回 docx，Content-Type 正确，body 非空
- `POST /api/convert` monkeypatch `converter.convert_file` 抛 `DependencyNotFoundError` → 500
- `POST /api/convert` 含 mermaid 文本时 monkeypatch 断言**调用了** `mermaid.preprocess`
- `sanitize_filename`：含路径、特殊字符、空、超长 各场景

### 8.2 集成测试（`@pytest.mark.integration`，默认跳过）
- 真实 pandoc：上传 `tests/fixtures/with_mermaid.md` → 预览成功 → 下载 docx 非空
- 真实 pandoc：纯文本预览成功（需本机有 pandoc；含 mermaid 的下载需 mmdc）

### 8.3 前端
不写自动化测试。手动验证清单（写入 README）：上传、编辑、预览、下载、错误 toast、mermaid 提示。

## 9. 完成标准

- [ ] `pip install -e ".[web,dev]"` 成功，`md2doc-web` 命令可启动
- [ ] 单元测试全部通过（原 76 + 新增 ~13，原 2 + 新增 1 集成测试默认跳过）
- [ ] 核心覆盖率 ≥ 90%（新增 `web/` 模块纯逻辑部分）
- [ ] `ruff check src/ tests/` 无错误
- [ ] 手动验证：浏览器访问 `http://localhost:8000`，上传 `tests/fixtures/with_mermaid.md` → 编辑框显示内容 → 预览区显示渲染 HTML（mermaid 块带提示）→ 点击下载得到 `with_mermaid.docx`，打开后图片可见
- [ ] 手动验证：直接在编辑框输入 markdown，预览实时更新
- [ ] 手动验证：上传非 .md 文件 → 看到错误 toast
- [ ] CLI `md2doc` 原功能不受影响（回归测试通过）

## 10. 安全与运维考虑

- 内网部署，无认证（设计取舍）
- 文件上传限制 10MB，防止内存爆炸
- 所有转换在 `TemporaryDirectory` 中进行，请求结束自动清理
- CodeMirror 与依赖走 HTTPS CDN（`esm.sh`），离线内网环境需提前镜像或换成本地静态文件（follow-up，非本次范围）
- pandoc/mmdc 都是 shell 调用，输入参数完全由代码控制（不接受用户传参），不存在命令注入
- `sanitize_filename` 防止 `Content-Disposition` 注入

## 11. 后续可能的扩展（非本次范围）

- 多格式下载（PDF/HTML/EPUB）
- 文档历史/持久化
- 用户认证
- 客户端 markdown 渲染（离线预览）
- CodeMirror 本地化打包（无 CDN 依赖）
