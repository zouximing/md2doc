import { EditorState } from "https://esm.sh/@codemirror/state@^6.0.0";
import { EditorView, keymap } from "https://esm.sh/@codemirror/view@^6.0.0";
import { defaultKeymap, history, historyKeymap } from "https://esm.sh/@codemirror/commands@^6.0.0";
import { markdown, markdownLanguage } from "https://esm.sh/@codemirror/lang-markdown@^6.0.0";
import { languages } from "https://esm.sh/@codemirror/language-data@^6.0.0";

const SAMPLE = `# 标题

这是一段 **测试** 文本。

- 项目一
- 项目二

\`\`\`mermaid
graph TD
    A-->B
\`\`\`
`;

const editorParent = document.getElementById("editor");
const previewEl = document.getElementById("preview");
const fileInput = document.getElementById("file-input");
const filenameLabel = document.getElementById("filename-label");
const downloadBtn = document.getElementById("download-btn");
const toastEl = document.getElementById("toast");
const previewLoading = document.getElementById("preview-loading");

let currentFilename = null;
let previewRequestId = 0;
let debounceTimer = null;

// --- 编辑器 ---
const view = new EditorView({
  state: EditorState.create({
    doc: SAMPLE,
    extensions: [
      history(),
      keymap.of([...defaultKeymap, ...historyKeymap]),
      markdown({ base: markdownLanguage, codeLanguages: languages }),
      EditorView.lineWrapping,
      EditorView.updateListener.of((update) => {
        if (update.docChanged) schedulePreview();
      }),
    ],
  }),
  parent: editorParent,
});

// --- 防抖预览 ---
function schedulePreview() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(runPreview, 600);
}

async function runPreview() {
  const myId = ++previewRequestId;
  const text = view.state.doc.toString();
  previewLoading.classList.remove("hidden");
  try {
    const res = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (myId !== previewRequestId) return;  // 过期响应
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "预览失败" }));
      throw new Error(err.detail || "预览失败");
    }
    const data = await res.json();
    renderPreview(data.html);
  } catch (e) {
    showToast(e.message);
  } finally {
    if (myId === previewRequestId) previewLoading.classList.add("hidden");
  }
}

function renderPreview(html) {
  // 保留 loading dot
  previewEl.innerHTML = html;
  previewEl.prepend(previewLoading);
  // 给 mermaid 代码块加提示
  previewEl.querySelectorAll("code.language-mermaid, pre.mermaid, pre code.mermaid").forEach((code) => {
    const pre = code.closest("pre");
    if (pre && !pre.previousElementSibling?.classList?.contains("mermaid-hint")) {
      const hint = document.createElement("div");
      hint.className = "mermaid-hint";
      hint.textContent = "下载 .docx 时此图会被渲染";
      pre.parentNode.insertBefore(hint, pre);
    }
  });
}

// --- 上传 ---
fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "上传失败" }));
      throw new Error(err.detail);
    }
    const data = await res.json();
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: data.text },
    });
    currentFilename = data.filename;
    filenameLabel.textContent = data.filename;
    runPreview();
  } catch (e) {
    showToast(e.message);
  } finally {
    fileInput.value = "";  // 允许重选同一文件
  }
});

// --- 下载 ---
downloadBtn.addEventListener("click", async () => {
  downloadBtn.disabled = true;
  const oldText = downloadBtn.textContent;
  downloadBtn.textContent = "生成中...";
  try {
    const text = view.state.doc.toString();
    const res = await fetch("/api/convert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, filename: currentFilename }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "下载失败" }));
      throw new Error(err.detail);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const stem = currentFilename ? currentFilename.replace(/\.[^.]+$/, "") : "document";
    a.href = url;
    a.download = stem + ".docx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    showToast(e.message);
  } finally {
    downloadBtn.disabled = false;
    downloadBtn.textContent = oldText;
  }
});

// --- toast ---
let toastTimer = null;
function showToast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.remove("hidden");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.add("hidden"), 3000);
}

// 首次预览
runPreview();
