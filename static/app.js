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
    if (body && typeof body === "object" && body.detail) {
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
    await api("/api/v1/documents/" + doc.id + "/reindex", { method: "POST" });
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
    const doc = await api("/api/v1/documents/upload", { method: "POST", body: form });
    toast('已入库「' + doc.filename + '」，共 ' + doc.chunk_count + " 个切块");
    await loadDocuments();
  } catch (e) {
    toast("上传失败：" + e.message, true);
  } finally {
    progress.classList.add("hidden");
  }
}

/* ================= 会话管理 ================= */

async function loadConversations() {
  try {
    const convs = await api("/api/v1/conversations");
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
    detail.messages.forEach((m) => appendMessage(m.role, m.content, m.citations || []));
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

function appendMessage(role, content, citations) {
  const box = $("#chat-messages");
  const empty = $("#chat-empty");
  if (empty) empty.remove();

  const wrap = document.createElement("div");
  wrap.className = "msg " + role;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;
  wrap.appendChild(bubble);

  if (role === "assistant" && citations) {
    const cites = document.createElement("div");
    if (citations.length) {
      cites.className = "cites";
      let html =
        '<div class="cites-title">📎 引用来源（' + citations.length + "，点击展开原文）</div>";
      citations.forEach((c) => {
        html +=
          '<details class="cite"><summary>' +
          '<span class="cite-file">' + escapeHtml(c.document_filename) + "</span>" +
          '<span class="cite-idx">#块 ' + c.chunk_index + "</span>" +
          '<span class="cite-score">' + (c.score != null ? c.score.toFixed(3) : "") + "</span>" +
          "</summary>" +
          '<div class="cite-content">' + escapeHtml(c.content) + "</div>" +
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
    const r = await postJson("/api/v1/chat", payload);
    hideTyping();
    state.conversationId = r.conversation_id;
    appendMessage("assistant", r.answer, r.citations);
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
    t.addEventListener("click", () => switchTab(t.dataset.tab));
  });
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
