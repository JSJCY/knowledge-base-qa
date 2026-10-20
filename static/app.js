"use strict";

/* ================= 工具函数 ================= */

const $ = (sel) => document.querySelector(sel);

async function api(path, options) {
  const resp = await fetch(path, options || {});
  if (resp.status === 204) return null;
  const ctype = resp.headers.get("content-type") || "";
  const isJson = ctype.includes("application/json");
  const body = isJson ? await resp.json() : await resp.text();
  if (!resp.ok) {
    let detail = "请求失败（HTTP " + resp.status + "）";
    if (body && typeof body === "object" && body.error) {
      detail = body.error.message || JSON.stringify(body.error);
    } else if (body && typeof body === "object" && body.detail) {
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    }
    throw new Error(detail);
  }
  return body;
}

function postJson(path, payload) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const markdownCodeBlocks = new Map();
let markdownCodeSequence = 0;
const citationStore = new Map();
let citationSequence = 0;

function highlightCode(code, language) {
  let html = escapeHtml(code);
  if (["js", "javascript", "ts", "typescript", "python", "py"].includes(language)) {
    html = html.replace(/\b(const|let|var|function|return|if|else|for|while|def|class|import|from|async|await|True|False|None)\b/g,
      '<span class="token-keyword">$1</span>');
  }
  if (["json", "js", "javascript"].includes(language)) {
    html = html.replace(/(&quot;[^&]*?&quot;)(?=\s*:)/g, '<span class="token-property">$1</span>');
  }
  return html;
}

function renderTable(block) {
  const rows = block.trim().split("\n").map((row) => row.replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim()));
  if (rows.length < 3 || !rows[1].every((cell) => /^:?-{3,}:?$/.test(cell))) return block;
  const head = rows[0].map((cell) => "<th>" + cell + "</th>").join("");
  const body = rows.slice(2).map((row) => "<tr>" + row.map((cell) => "<td>" + cell + "</td>").join("") + "</tr>").join("");
  return "<div class=\"table-wrap\"><table><thead><tr>" + head + "</tr></thead><tbody>" + body + "</tbody></table></div>";
}

// 轻量 Markdown 渲染器：先完整转义，再处理受控语法，避免模型输出被当作 HTML 执行。
function renderMarkdown(source) {
  let raw = String(source || "").replace(/\r\n?/g, "\n");
  const codeBlocks = [];
  const mathBlocks = [];
  const inlineMath = [];
  raw = raw.replace(/```([\w+-]*)\n?([\s\S]*?)```/g, (_, language, code) => {
    const id = "code-" + (++markdownCodeSequence);
    markdownCodeBlocks.set(id, code.trimEnd());
    codeBlocks.push('<pre class="code-block"><div class="code-toolbar"><span>' + escapeHtml(language || "text") + '</span><button class="code-copy" data-code-id="' + id + '">复制</button></div><code>' + highlightCode(code.trimEnd(), language.toLowerCase()) + '</code></pre>');
    return "\n@@CODE" + (codeBlocks.length - 1) + "@@\n";
  });
  raw = raw.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) => {
    mathBlocks.push('<div class="math-block">' + escapeHtml(formula.trim()) + '</div>');
    return "\n@@MATH" + (mathBlocks.length - 1) + "@@\n";
  });
  raw = raw.replace(/\$([^$\n]+)\$/g, (_, formula) => {
    inlineMath.push('<span class="math-inline">' + escapeHtml(formula) + "</span>");
    return "@@INLINE_MATH" + (inlineMath.length - 1) + "@@";
  });
  let text = escapeHtml(raw);
  text = text.replace(/^###### (.*)$/gm, "<h6>$1</h6>")
    .replace(/^##### (.*)$/gm, "<h5>$1</h5>")
    .replace(/^#### (.*)$/gm, "<h4>$1</h4>")
    .replace(/^### (.*)$/gm, "<h3>$1</h3>")
    .replace(/^## (.*)$/gm, "<h2>$1</h2>")
    .replace(/^# (.*)$/gm, "<h1>$1</h1>")
    .replace(/^> (.*)$/gm, "<blockquote>$1</blockquote>")
    .replace(/^[-*] (.*)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>\n?)+/g, (list) => "<ul>" + list + "</ul>")
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_\n]+)__/g, "<strong>$1</strong>")
    .replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  text = text.replace(/(^\|.+\|\n\|(?:\s*:?-{3,}:?\s*\|)+\n(?:\|.+\|\n?)+)/gm, renderTable);
  text = text.split(/\n{2,}/).map((block) => /^(<(h[1-6]|ul|blockquote|div)|@@(?:CODE|MATH))/.test(block.trim())
    ? block : "<p>" + block.replace(/\n/g, "<br>") + "</p>").join("");
  return text
    .replace(/@@CODE(\d+)@@/g, (_, i) => codeBlocks[Number(i)])
    .replace(/@@MATH(\d+)@@/g, (_, i) => mathBlocks[Number(i)])
    .replace(/@@INLINE_MATH(\d+)@@/g, (_, i) => inlineMath[Number(i)]);
}

async function copyCode(id) {
  const code = markdownCodeBlocks.get(id);
  if (code == null) return;
  try {
    await navigator.clipboard.writeText(code);
    toast("代码已复制");
  } catch (_) {
    const input = document.createElement("textarea");
    input.value = code;
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    input.remove();
    toast("代码已复制");
  }
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
}

let toastTimer = null;
function toast(msg, isErr) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast" + (isErr ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 3200);
}

/* ================= 全局状态 ================= */

const state = {
  conversationId: null, // 当前会话（null = 下次提问开新会话）
  sending: false,
  documents: [],
};

/* ================= 顶栏信息 ================= */

async function loadInfo() {
  const badge = $("#llm-badge");
  const ver = $("#version-badge");
  try {
    const info = await api("/api/v1/info");
    ver.textContent = "v" + info.version;
    if (info.llm_enabled) {
      badge.textContent = "● DeepSeek 已连接";
      badge.className = "badge";
    } else {
      badge.textContent = "● Mock 模式（未配置 Key）";
      badge.className = "badge warn";
    }
  } catch (e) {
    badge.textContent = "● 后端未连接";
    badge.className = "badge err";
  }
}

/* ================= 文档管理 ================= */

async function loadDocuments() {
  try {
    const data = await api("/api/v1/documents?limit=100");
    state.documents = data.items;
    renderDocuments();
    renderSearchDocFilter();
  } catch (e) {
    toast("加载文档列表失败：" + e.message, true);
  }
}

function renderDocuments() {
  const ul = $("#doc-list");
  ul.innerHTML = "";
  if (!state.documents.length) {
    const li = document.createElement("li");
    li.className = "doc-meta";
    li.style.padding = "4px 6px";
    li.textContent = "暂无文档，先上传一份吧～";
    ul.appendChild(li);
    return;
  }
  state.documents.forEach((doc) => {
    const li = document.createElement("li");
    li.className = "doc-item";

    const info = document.createElement("div");
    info.className = "doc-info";
    const indexed = doc.status === "indexed";
    info.innerHTML =
      '<span class="doc-name" title="' + escapeHtml(doc.filename) + '">📄 ' +
      escapeHtml(doc.filename) + "</span>" +
      '<span class="doc-meta"><span class="status-dot' + (indexed ? "" : " pending") + '"></span>' +
      (indexed ? "已索引" : "待索引") + " · " + doc.chunk_count + " 块 · " +
      formatSize(doc.size_bytes) + "</span>";

    const actions = document.createElement("div");
    actions.className = "doc-actions";

    const reindexBtn = document.createElement("button");
    reindexBtn.className = "icon-btn";
    reindexBtn.title = "重新向量化";
    reindexBtn.textContent = "⟳";
    reindexBtn.onclick = () => reindexDocument(doc);

    const delBtn = document.createElement("button");
    delBtn.className = "icon-btn danger";
    delBtn.title = "删除文档";
    delBtn.textContent = "✕";
    delBtn.onclick = () => deleteDocument(doc);

    actions.appendChild(reindexBtn);
    actions.appendChild(delBtn);
    li.appendChild(info);
    li.appendChild(actions);
    ul.appendChild(li);
  });
}

async function reindexDocument(doc) {
  toast("正在重新向量化：" + doc.filename + " …");
  try {
    const task = await api("/api/v1/documents/" + doc.id + "/reindex/async", { method: "POST" });
    await waitForTask(task, "正在重新向量化");
    toast("已重建索引：" + doc.filename);
    loadDocuments();
  } catch (e) {
    toast("重建索引失败：" + e.message, true);
  }
}

async function deleteDocument(doc) {
  if (!confirm('删除文档「' + doc.filename + '」？其切块与向量将一并删除。')) return;
  try {
    await api("/api/v1/documents/" + doc.id, { method: "DELETE" });
    toast("已删除：" + doc.filename);
    loadDocuments();
  } catch (e) {
    toast("删除失败：" + e.message, true);
  }
}

/* ================= 文档上传 ================= */

function bindUpload() {
  const zone = $("#drop-zone");
  const input = $("#file-input");
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") input.click();
  });
  input.addEventListener("change", () => {
    if (input.files.length) uploadFile(input.files[0]);
    input.value = "";
  });
  ["dragenter", "dragover"].forEach((ev) =>
    zone.addEventListener(ev, (e) => {
      e.preventDefault();
      zone.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach((ev) =>
    zone.addEventListener(ev, (e) => {
      e.preventDefault();
      zone.classList.remove("dragover");
    })
  );
  zone.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) uploadFile(f);
  });
}

async function uploadFile(file) {
  const progress = $("#upload-progress");
  const text = $("#upload-text");
  progress.classList.remove("hidden");
  text.textContent = "正在上传并向量化 " + file.name + " …";
  try {
    const form = new FormData();
    form.append("file", file);
    const task = await api("/api/v1/documents/upload/async", { method: "POST", body: form });
    const completed = await waitForTask(task, "正在解析并向量化");
    const doc = await api("/api/v1/documents/" + completed.document_id);
    toast('已入库「' + doc.filename + '」，共 ' + doc.chunk_count + " 个切块");
    await loadDocuments();
  } catch (e) {
    toast("上传失败：" + e.message, true);
  } finally {
    progress.classList.add("hidden");
  }
}

async function waitForTask(task, label) {
  for (let attempt = 0; attempt < 150; attempt += 1) {
    const current = await api("/api/v1/documents/tasks/" + task.id);
    if (current.status === "completed") return current;
    if (current.status === "failed") throw new Error(current.error || "后台任务失败");
    $("#upload-text").textContent = label + "（" + current.progress + "%）…";
    await new Promise((resolve) => setTimeout(resolve, 800));
  }
  throw new Error("后台任务处理超时，请稍后在文档列表查看状态");
}

/* ================= 会话管理 ================= */

async function loadConversations() {
  try {
    const query = $("#conv-search") ? $("#conv-search").value.trim() : "";
    const convs = await api("/api/v1/conversations" + (query ? "?q=" + encodeURIComponent(query) : ""));
    renderConversations(convs);
  } catch (e) {
    /* 静默：会话列表非关键路径 */
  }
}

function renderConversations(convs) {
  const ul = $("#conv-list");
  ul.innerHTML = "";
  if (!convs.length) {
    const li = document.createElement("li");
    li.className = "doc-meta";
    li.style.padding = "4px 6px";
    li.textContent = "暂无历史会话";
    ul.appendChild(li);
    return;
  }
  convs.forEach((conv) => {
    const li = document.createElement("li");
    li.className = "conv-item" + (conv.id === state.conversationId ? " active" : "");
    li.innerHTML =
      '<span class="conv-title" title="' + escapeHtml(conv.title) + '">💬 ' +
      escapeHtml(conv.title || "新会话") + "</span>" +
      '<span class="conv-count">' + conv.message_count + " 条</span>";

    const del = document.createElement("button");
    del.className = "icon-btn danger";
    del.textContent = "✕";
    del.title = "删除会话";
    del.onclick = async (e) => {
      e.stopPropagation();
      if (!confirm("删除该会话及其全部消息？")) return;
      try {
        await api("/api/v1/conversations/" + conv.id, { method: "DELETE" });
        if (state.conversationId === conv.id) newChat();
        loadConversations();
      } catch (err) {
        toast("删除会话失败：" + err.message, true);
      }
    };

    li.onclick = () => openConversation(conv.id);
    const rename = document.createElement("button");
    rename.className = "icon-btn";
    rename.textContent = "✎";
    rename.title = "重命名会话";
    rename.onclick = async (e) => {
      e.stopPropagation();
      const title = prompt("会话名称", conv.title);
      if (!title || !title.trim()) return;
      await api("/api/v1/conversations/" + conv.id, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: title.trim() }) });
      loadConversations();
    };
    li.appendChild(rename);
    li.appendChild(del);
    ul.appendChild(li);
  });
}

async function openConversation(id) {
  try {
    const detail = await api("/api/v1/conversations/" + id);
    state.conversationId = id;
    switchTab("chat");
    const box = $("#chat-messages");
    box.innerHTML = "";
    detail.messages.forEach((m) => appendMessage(m.role, m.content, m.citations || [], m.id, m.feedback));
    loadConversations();
  } catch (e) {
    toast("打开会话失败：" + e.message, true);
  }
}

function newChat() {
  state.conversationId = null;
  const box = $("#chat-messages");
  box.innerHTML =
    '<div class="empty-hint" id="chat-empty">' +
    '<div class="empty-icon">📚</div>' +
    "<p>先在左侧上传文档，然后开始提问吧</p>" +
    '<p class="sub">回答会附带知识库引用来源；知识库中找不到时会如实告知</p>' +
    "</div>";
  loadConversations();
}

/* ================= 聊天 ================= */

function appendMessage(role, content, citations, messageId, feedback) {
  const box = $("#chat-messages");
  const empty = $("#chat-empty");
  if (empty) empty.remove();

  const wrap = document.createElement("div");
  wrap.className = "msg " + role;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = role === "assistant" ? renderMarkdown(content) : escapeHtml(content).replace(/\n/g, "<br>");
  wrap.appendChild(bubble);
  if (role === "assistant" && messageId) {
    const actions = document.createElement("div");
    actions.className = "message-actions";
    ["up", "down"].forEach((value) => {
      const button = document.createElement("button");
      button.className = "feedback-btn" + (feedback === value ? " active" : "");
      button.textContent = value === "up" ? "👍" : "👎";
      button.onclick = async () => {
        await postJson("/api/v1/conversations/" + state.conversationId + "/messages/" + messageId + "/feedback", { feedback: value });
        button.parentElement.querySelectorAll(".feedback-btn").forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
      };
      actions.appendChild(button);
    });
    wrap.appendChild(actions);
  }

  if (role === "assistant" && citations) {
    const cites = document.createElement("div");
    if (citations.length) {
      cites.className = "cites";
      let html =
        '<div class="cites-title">📎 引用来源（' + citations.length + "，点击展开原文）</div>";
      citations.forEach((c) => {
        const citationId = "citation-" + (++citationSequence);
        citationStore.set(citationId, c);
        html +=
          '<details class="cite"><summary>' +
          '<span class="cite-file">' + (c.source_id ? '[S' + c.source_id + '] ' : '') + escapeHtml(c.document_filename) + "</span>" +
          '<span class="cite-idx">#块 ' + c.chunk_index + "</span>" +
          '<span class="cite-score">' + (c.score != null ? c.score.toFixed(3) : "") + "</span>" +
          "</summary>" +
          '<div class="cite-content">' + escapeHtml(c.content) + "</div>" +
          '<button class="cite-locate" data-citation-id="' + citationId + '">在检索面板中定位</button>' +
          "</details>";
      });
      cites.innerHTML = html;
    } else {
      cites.className = "cites none";
      cites.innerHTML = '<div class="cites-title">⚠️ 知识库中未检索到相关内容</div>';
    }
    wrap.appendChild(cites);
  }

  box.appendChild(wrap);
  box.scrollTop = box.scrollHeight;
  return wrap;
}

function locateCitation(citation) {
  switchTab("search");
  $("#search-doc").value = String(citation.document_id);
  $("#search-input").value = citation.content;
  const box = $("#search-results");
  box.innerHTML =
    '<div class="source-location">' +
    '<div class="result-head"><span class="result-file">📍 ' + escapeHtml(citation.document_filename) + '</span>' +
    '<span class="result-idx">#块 ' + citation.chunk_index + '</span></div>' +
    '<div class="result-content">' + escapeHtml(citation.content) + "</div>" +
    '<button id="btn-source-search" class="btn">查看相邻检索结果</button></div>';
  $("#btn-source-search").addEventListener("click", runSearch);
}

function appendStreamingMessage() {
  const wrap = appendMessage("assistant", "", null);
  wrap.classList.add("streaming");
  return { wrap, bubble: wrap.querySelector(".bubble") };
}

async function streamQuestion(path, payload, onDelta, onDone) {
  const resp = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw new Error("请求失败（HTTP " + resp.status + "）");
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const events = buffer.split("\n\n");
    buffer = events.pop();
    for (const raw of events) {
      const event = raw.match(/^event: (.+)\ndata: (.+)$/s);
      if (!event) continue;
      const data = JSON.parse(event[2]);
      if (event[1] === "delta") onDelta(data.content || "");
      if (event[1] === "done") onDone(data);
      if (event[1] === "error") throw new Error(data.detail || "流式问答失败");
    }
    if (done) break;
  }
}

function appendErrorMessage(msg) {
  const wrap = appendMessage("assistant", "⚠️ " + msg, null);
  const bubble = wrap.querySelector(".bubble");
  if (bubble) bubble.classList.add("error");
}

function showTyping() {
  const box = $("#chat-messages");
  const empty = $("#chat-empty");
  if (empty) empty.remove();
  const wrap = document.createElement("div");
  wrap.className = "msg assistant typing";
  wrap.id = "typing-indicator";
  wrap.innerHTML =
    '<div class="bubble"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';
  box.appendChild(wrap);
  box.scrollTop = box.scrollHeight;
}

function hideTyping() {
  const el = $("#typing-indicator");
  if (el) el.remove();
}

async function sendQuestion() {
  if (state.sending) return;
  const input = $("#chat-input");
  const question = input.value.trim();
  if (!question) return;

  state.sending = true;
  $("#btn-send").disabled = true;
  input.value = "";
  input.style.height = "auto";

  appendMessage("user", question, null);
  showTyping();

  try {
    const payload = { question: question, top_k: 5 };
    if (state.conversationId != null) payload.conversation_id = state.conversationId;
    hideTyping();
    const streamed = appendStreamingMessage();
    let answer = "";
    const r = await streamQuestion("/api/v1/chat/stream", payload, (part) => {
      answer += part;
      streamed.bubble.innerHTML = renderMarkdown(answer);
      $("#chat-messages").scrollTop = $("#chat-messages").scrollHeight;
    }, (data) => {
      state.conversationId = data.conversation_id;
      const finalWrap = appendMessage("assistant", answer, data.citations || []);
      streamed.wrap.replaceWith(finalWrap);
    });
    loadConversations();
  } catch (e) {
    hideTyping();
    appendErrorMessage(e.message);
  } finally {
    state.sending = false;
    $("#btn-send").disabled = false;
    input.focus();
  }
}

function bindChat() {
  const input = $("#chat-input");
  $("#btn-send").addEventListener("click", sendQuestion);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendQuestion();
    }
  });
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  });
  $("#btn-new-chat").addEventListener("click", newChat);
  $("#conv-search").addEventListener("input", () => {
    clearTimeout(state.conversationSearchTimer);
    state.conversationSearchTimer = setTimeout(loadConversations, 250);
  });
  document.addEventListener("click", (event) => {
    const copyButton = event.target.closest(".code-copy");
    if (copyButton) copyCode(copyButton.dataset.codeId);
    const locateButton = event.target.closest(".cite-locate");
    if (locateButton) locateCitation(citationStore.get(locateButton.dataset.citationId));
  });
}

/* ================= 检索面板 ================= */

function renderSearchDocFilter() {
  const sel = $("#search-doc");
  const current = sel.value;
  sel.innerHTML = '<option value="">全部文档</option>';
  state.documents.forEach((d) => {
    const opt = document.createElement("option");
    opt.value = String(d.id);
    opt.textContent = d.filename;
    sel.appendChild(opt);
  });
  sel.value = state.documents.some((d) => String(d.id) === current) ? current : "";
}

async function runSearch() {
  const query = $("#search-input").value.trim();
  if (!query) {
    toast("请先输入要检索的内容");
    return;
  }
  const payload = { query: query, top_k: parseInt($("#search-topk").value, 10) };
  const docId = $("#search-doc").value;
  if (docId) payload.document_id = parseInt(docId, 10);

  const box = $("#search-results");
  box.innerHTML = '<div class="empty-hint"><p><span class="spinner"></span> 检索中…</p></div>';
  try {
    const r = await postJson("/api/v1/search", payload);
    if (!r.results.length) {
      box.innerHTML =
        '<div class="empty-hint"><div class="empty-icon">🤔</div>' +
        "<p>没有找到相关内容，试试其他关键词或先上传文档</p></div>";
      return;
    }
    box.innerHTML = "";
    r.results.forEach((item) => {
      const pct = Math.max(0, Math.min(100, Math.round(item.score * 100)));
      const card = document.createElement("div");
      card.className = "result-card";
      card.innerHTML =
        '<div class="result-head">' +
        '<span class="result-file">📄 ' + escapeHtml(item.document_filename) + "</span>" +
        '<span class="result-idx">#块 ' + item.chunk_index + "</span>" +
        '<span class="result-score"><span class="score-num">' + item.score.toFixed(3) + "</span>" +
        '<span class="score-bar"><span class="score-fill" style="width:' + pct + '%"></span></span></span>' +
        "</div>" +
        '<div class="result-content">' + escapeHtml(item.content) + "</div>";
      box.appendChild(card);
    });
  } catch (e) {
    box.innerHTML =
      '<div class="empty-hint"><div class="empty-icon">⚠️</div><p>检索失败：' +
      escapeHtml(e.message) + "</p></div>";
  }
}

function bindSearch() {
  $("#btn-search").addEventListener("click", runSearch);
  $("#search-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") runSearch();
  });
}

/* ================= 标签页 ================= */

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.tab === name);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.id === "tab-" + name);
  });
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => { switchTab(t.dataset.tab); if (t.dataset.tab === "admin") loadAdminOverview(); });
  });
}

async function loadAdminOverview() {
  const box = $("#admin-stats");
  box.textContent = "加载中…";
  try {
    const data = await api("/api/v1/admin/overview");
    const stats = [["文档", data.document_count], ["已索引", data.indexed_document_count], ["会话", data.conversation_count], ["消息", data.message_count], ["好评", data.feedback_up_count], ["差评", data.feedback_down_count]];
    box.innerHTML = stats.map((item) => '<div class="stat-card"><strong>' + item[1] + "</strong><span>" + item[0] + "</span></div>").join("");
  } catch (e) { box.textContent = "加载失败：" + e.message; }
}

/* ================= 初始化 ================= */

document.addEventListener("DOMContentLoaded", () => {
  loadInfo();
  loadDocuments();
  loadConversations();
  bindUpload();
  bindChat();
  bindSearch();
  bindTabs();
  $("#chat-input").focus();
});
