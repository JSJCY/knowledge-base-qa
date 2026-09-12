# 更新日志

本文件采用“功能分阶段”记录方式。项目尚未发布新的正式版本，以下内容均位于当前 `main` 分支的未发布版本中。

## 第四阶段：会话体验与管理概览

提交：`64253da feat: improve conversations and add admin overview`

### 新增

- 左侧历史会话支持按标题和消息内容搜索。
- 支持点击 `✎` 重命名会话。
- 已保存的历史回答可提交 👍 / 👎 反馈。
- 新增会话 Markdown 导出接口：`GET /api/v1/conversations/{conversation_id}/export`。
- 新增 `📊 管理` 页面，展示文档、已索引文档、会话、消息与回答反馈统计。
- 新增管理概览接口：`GET /api/v1/admin/overview`。

### 使用提示

- 回答反馈按钮在重新打开一段已保存的历史会话后显示。
- 管理概览点击顶部的 `📊 管理` 标签页即可查看。

## 第三阶段：安全与数据治理

提交：`cf923ce feat: add auth and document governance`

### 新增

- 可选本地账户注册与登录，使用 Bearer Token 认证。
- 开启认证后，文档和会话会按用户隔离。
- 上传文件增加 PDF 签名及二进制内容检查。
- RAG 提示词将知识库资料标记为非可信内容，忽略其中试图改变模型角色或绕过规则的指令。
- 文档支持 SHA-256 内容去重、同名版本号、软删除和恢复。

### 配置

默认不启用账户认证，以保持本地单用户体验。需要启用时，在 `.env` 中设置：

```ini
AUTH_ENABLED=true
AUTH_TOKEN_EXPIRE_HOURS=24
```

认证接口：

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`

## 第二阶段：异步任务与运行工程化

提交：`692cc5d feat: add background tasks and api operations`

### 新增

- 文档异步上传与索引：`POST /api/v1/documents/upload/async`。
- 后台任务状态查询：`GET /api/v1/documents/tasks/{task_id}`。
- 前端上传和重建索引改为轮询任务进度。
- API 统一错误结构与 `X-Request-ID` 请求追踪。
- 可选 API Key 鉴权及单 IP 限流。
- 新增 Dockerfile、Docker Compose 和 Nginx 反向代理配置。
- 增加 Alembic 迁移配置入口和迁移说明。

### 配置

```ini
API_KEY=
RATE_LIMIT_PER_MINUTE=120
```

`API_KEY` 留空时不启用 API Key 校验。

## 第一阶段：回答呈现与 RAG 质量

提交：`5e74f05 feat: enhance markdown and rag retrieval`

### 新增

- Markdown 支持表格、公式样式、代码块高亮和一键复制。
- 引用来源可定位到检索面板中的原始片段。
- 检索升级为向量语义与关键词命中的混合召回，并进行融合重排序。
- 支持低相关性拒答，减少无依据回答。
- 多轮会话自动压缩过长历史上下文。
- 可选使用模型把追问改写成独立检索问题。

### 配置

```ini
RAG_HISTORY_CHAR_BUDGET=6000
RAG_MIN_RELEVANCE_SCORE=0.15
RAG_CANDIDATE_MULTIPLIER=3
RAG_VECTOR_WEIGHT=0.7
RAG_KEYWORD_WEIGHT=0.3
RAG_QUERY_REWRITE_ENABLED=false
```

`RAG_QUERY_REWRITE_ENABLED=true` 会额外消耗一次模型调用。

## 流式回答与基础 Markdown

提交：`e5b6321 feat: add streaming chat and markdown rendering`

### 新增

- 新增 SSE 流式问答接口：`POST /api/v1/chat/stream`。
- 前端回答内容实时增量显示。
- 支持标题、列表、引用、链接、粗体和代码块等基础 Markdown。
- 流式回答完成后自动保存会话、回答和引用来源。

## 升级后看不到页面变化？

1. 重启服务：`.venv\Scripts\uvicorn app.main:app --reload`
2. 浏览器按 `Ctrl + F5` 强制刷新静态资源。
3. 确认访问的是当前项目的 `http://127.0.0.1:8000/`。
