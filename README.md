# 知识库问答系统（Knowledge Base QA）

[![CI](https://github.com/JSJCY/knowledge-base-qa/actions/workflows/ci.yml/badge.svg)](https://github.com/JSJCY/knowledge-base-qa/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![Evaluation](https://img.shields.io/badge/RAG-evaluation-blue)](docs/EVALUATION.md)
[![Release](https://img.shields.io/github/v/release/JSJCY/knowledge-base-qa)](https://github.com/JSJCY/knowledge-base-qa/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

基于 **FastAPI + 本地向量检索（RAG）+ DeepSeek** 的知识库问答系统：

> 上传文档（.txt / .md / .pdf）→ 自动解析切块 → **本地向量化**（BGE 中文模型，免费离线）→ 提问时检索最相关内容 → **DeepSeek 生成带引用来源的回答**，支持多轮会话上下文。

详细功能变化与启用方式见 [更新日志](CHANGELOG.md)。

生产环境部署见 [部署指南](DEPLOYMENT.md)。

## ✨ 特性

- 📄 **文档管理**：上传 / 列表 / 详情 / 切块查看 / 删除；支持 TXT、Markdown、PDF，兼容 UTF-8 与 GB18030 中文编码
- 🧩 **智能切块**：段落感知打包 + 超长段落窗口硬切 + 块间重叠，兼顾语义完整与检索粒度
- 🧠 **本地向量化**：fastembed + `BAAI/bge-small-zh-v1.5`（ONNX 本地推理，无需付费 embedding API，模型仅首次下载）
- 🔍 **混合检索**：融合向量语义与关键词命中，候选集重排序，降低专有名词漏召回；支持全库检索或限定单文档
- 💬 **RAG 问答**：支持低相关拒答、上下文压缩与可选查询改写；回答自动附带引用来源（文档名 / 段落号 / 相似度）
- 🗂 **多轮会话**：会话与消息持久化（SQLite），自动生成会话标题，追问自动携带上下文
- 🖥 **Web 界面**：内置零依赖单页前端，支持流式回答、Markdown（表格 / 公式 / 代码块高亮与复制）、引用来源定位、文档拖拽上传与会话切换
- ⚙️ **工程化运行**：文档可异步入队处理并查询进度；统一错误格式、请求 ID、可选 API Key 与限流；提供 Docker Compose + Nginx 部署配置
- 🔌 **可插拔设计**：向量化与 LLM 均为依赖注入；未配置 API Key 时自动降级 Mock 模式，全流程仍可跑通
- ✅ **工程化**：pytest 功能回归、独立 RAG 质量评测、ruff 代码规范、GitHub Actions CI、Swagger 交互文档

## 🏗 工作原理

```
上传文档                     提问
   │                          │
   ▼                          ▼
解析文本(pypdf/编码探测)    问题向量化(BGE)
   │                          │
   ▼                          ▼
段落感知切块 ──► 向量化     余弦相似度检索 Top-K
   │                          │
   ▼                          ▼
SQLite(chunks+embedding)   组装 Prompt(资料+会话历史)
                              │
                              ▼
                        DeepSeek 生成回答
                              │
                              ▼
                    答案 + 引用来源 + 会话持久化
```

## 🚀 快速开始

### 1. 克隆并安装

```bash
git clone https://github.com/JSJCY/knowledge-base-qa.git
cd knowledge-base-qa
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"     # Windows
# source .venv/bin/activate && pip install -e ".[dev]"   # Linux/macOS
```

### 2. 配置

```bash
cp .env.example .env
```

在 `.env` 中填入 DeepSeek API Key（[platform.deepseek.com](https://platform.deepseek.com) 获取）：

```ini
DEEPSEEK_API_KEY=sk-xxxxxxxx
# 国内网络建议启用镜像，加速首次向量模型下载：
HF_ENDPOINT=https://hf-mirror.com
```

> 不填 Key 也能启动：问答接口自动进入 **Mock 模式**（返回占位回答），文档上传、切块、向量检索功能不受影响。

### 3. 启动

```bash
.venv\Scripts\uvicorn app.main:app --reload
```

- **Web 界面**：http://127.0.0.1:8000/ （上传文档、提问、检索，开箱即用）
- Swagger 交互文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

### 4. 使用

```bash
# ① 上传文档（自动解析、切块、向量化）
curl -X POST http://127.0.0.1:8000/api/v1/documents/upload -F "file=@产品手册.pdf"

# ② 提问（返回答案 + 引用来源 + 会话 ID）
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "这个产品怎么初始化？", "top_k": 5}'

# ③ 携带 conversation_id 追问（多轮上下文）
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "那它支持哪些配置项？", "conversation_id": 1}'

# ④ 纯检索（不走大模型）
curl -X POST http://127.0.0.1:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "初始化步骤", "top_k": 3}'
```

## 📚 API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | Web 前端界面（单页应用） |
| GET | `/health` | 健康检查 |
| GET | `/api/v1/info` | 服务信息（版本、LLM 是否启用） |
| POST | `/api/v1/documents/upload` | 上传文档（.txt / .md / .pdf，自动解析、切块、向量化） |
| POST | `/api/v1/documents/upload/async` | 异步上传与索引，返回任务 ID |
| GET | `/api/v1/documents/tasks/{task_id}` | 查询后台任务进度与错误信息 |
| GET | `/api/v1/documents` | 文档列表（分页） |
| GET | `/api/v1/documents/{id}` | 文档详情 |
| GET | `/api/v1/documents/{id}/chunks` | 文档切块列表 |
| POST | `/api/v1/documents/{id}/reindex` | 重新向量化文档 |
| DELETE | `/api/v1/documents/{id}` | 删除文档及其切块 |
| POST | `/api/v1/search` | 向量检索（余弦相似度排序） |
| POST | `/api/v1/chat` | 知识库问答（RAG，带引用来源，支持多轮会话） |
| GET | `/api/v1/conversations` | 会话列表 |
| GET | `/api/v1/conversations/{id}` | 会话详情（含消息与引用） |
| DELETE | `/api/v1/conversations/{id}` | 删除会话 |

完整参数与在线调试见 Swagger：`/docs`。

## ⚙️ 配置说明（.env）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 空 | DeepSeek 密钥；留空则问答走 Mock 模式 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容接口地址（可指向通义/Kimi 等） |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 对话模型名 |
| `LLM_TEMPERATURE` | `0.3` | 生成温度，越低越严谨 |
| `RAG_HISTORY_LIMIT` | `10` | 多轮对话携带的历史消息条数 |
| `RAG_HISTORY_CHAR_BUDGET` | `6000` | 多轮历史上下文的字符预算，超出部分压缩为摘要 |
| `RAG_MIN_RELEVANCE_SCORE` | `0.15` | 混合检索低于此分数时拒答，避免无依据生成 |
| `RAG_QUERY_REWRITE_ENABLED` | `false` | 是否使用模型将追问改写为独立检索问题（会增加一次模型调用） |
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | fastembed 向量模型 |
| `HF_ENDPOINT` | 空 | HuggingFace 镜像（国内建议 `https://hf-mirror.com`） |
| `DATABASE_URL` | `sqlite:///./kb.db` | 数据库连接串 |
| `UPLOAD_DIR` | `data/uploads` | 原始文件保存目录 |
| `MAX_UPLOAD_MB` | `20` | 单文件大小上限（MB） |
| `CHUNK_SIZE` | `500` | 切块目标长度（字符） |
| `CHUNK_OVERLAP` | `50` | 相邻切块重叠长度（字符） |
| `DEBUG` | `false` | FastAPI 调试模式 |
| `API_KEY` | 空 | 配置后 `/api/v1/*` 请求需携带 `X-API-Key` |
| `RATE_LIMIT_PER_MINUTE` | `120` | 单 IP 每分钟 API 请求上限 |

## 📁 项目结构

```
├── app/
│   ├── main.py                # 应用入口（create_app + lifespan 建表）
│   ├── core/
│   │   ├── config.py          # pydantic-settings 配置（.env 加载）
│   │   └── db.py              # SQLAlchemy 引擎 / 会话 / 建表
│   ├── api/routes/            # 路由层
│   │   ├── health.py          # 健康检查与服务信息
│   │   ├── documents.py       # 文档上传 / 管理 / 重建索引
│   │   ├── search.py          # 向量检索
│   │   └── chat.py            # RAG 问答与会话
│   ├── models/                # ORM：文档 / 切块(含向量) / 会话 / 消息
│   ├── schemas/               # Pydantic 请求响应模型
│   └── services/              # 业务层
│       ├── parsing.py         # txt/md/pdf → 文本（编码探测）
│       ├── chunking.py        # 段落感知切块 + 重叠
│       ├── embedding.py       # fastembed 向量化（懒加载、归一化）
│       ├── retrieval.py       # 余弦相似度 Top-K 检索
│       ├── llm.py             # DeepSeek 客户端 + Mock 降级
│       ├── rag.py             # 检索→Prompt→LLM→会话持久化编排
│       ├── documents.py       # 文档服务
│       └── conversations.py   # 会话服务
├── static/                    # Web 前端（原生 HTML/CSS/JS 单页应用，零构建）
│   ├── index.html             # 页面结构
│   ├── style.css              # 界面样式
│   └── app.js                 # 交互逻辑（上传/问答/检索/会话）
├── tests/                     # 功能与质量管线测试（CI 使用确定性依赖替身）
├── .github/workflows/ci.yml   # CI：ruff lint + pytest + coverage
├── pyproject.toml             # 依赖与工具配置
└── .env.example               # 配置模板
```

## 🧪 测试与质量

```bash
pytest --cov=app        # 工程测试；覆盖率不代表回答准确率
ruff check .            # 代码规范
```

测试策略：真实向量模型与 DeepSeek API 通过**依赖注入**替换为确定性假实现（词袋假向量器 / 回显假 LLM），因此 CI 无需下载模型、不消耗 API 额度、秒级完成；真实模型另行批量评测，保留原始输出、引用和评分理由；当前模型辅助评分尚待独立人工校准。

## 📖 FAQ

**首次上传/检索很慢？** 首次会下载向量模型（约 100MB，实测约 1 分钟），之后走本地缓存。国内请在 `.env` 设置 `HF_ENDPOINT=https://hf-mirror.com`。

**扫描版 PDF 能识别吗？** 不能。系统提取 PDF 文本层，扫描件无文本层会返回 422（可先 OCR 再上传）。

**数据存在哪里？** `kb.db`（SQLite：文档元数据、切块、向量、会话）与 `data/uploads/`（原始文件）。删除即重置，均不入库 Git。

**知识库能放多少文档？** 检索为内存暴力余弦相似度，数千切块内毫秒级响应；更大规模可替换 `retrieval.py` 为专用向量库（接口已隔离）。

**能换别的大模型吗？** 可以。`DEEPSEEK_BASE_URL` 指向任何 OpenAI 兼容接口（通义、Kimi、Moonshot、本地 vLLM 等），或在 `llm.py` 实现新的 `LLMService`。

## 🗺 开发路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| 1 | 项目骨架：配置管理、健康检查、测试与 CI | ✅ 完成 |
| 2 | 文档管理：上传 / 解析 / 切块 / 存储 | ✅ 完成 |
| 3 | 向量化与检索：embedding + 相似度搜索 | ✅ 完成 |
| 4 | RAG 问答：DeepSeek 接入、引用来源、会话历史 | ✅ 完成 |
| 5 | 交付收尾：文档、覆盖率、v1.0.0 发布 | ✅ 完成 |
| 6 | Web 前端：文档管理 / 问答聊天 / 检索面板界面 | ✅ 完成 |

## 📄 License

[MIT](LICENSE) © 2026 JSJCY

## RAG 质量评测（v1.2.0）

固定 60 条样本，覆盖中文、带干扰的多跳问答和项目边界场景。
支持真实检索评测、标准证据生成诊断、端到端评测、模型辅助语义评分和版本对比。
回答按事实关联 [S1] 引用，核验通过后展示；SSE 会等待核验完成再发送答案。
默认额外进行一次模型语义核验，增加延迟与费用；可配置关闭，但关闭后不应声称语义已验证。

详见 [评测与维护指南](docs/EVALUATION.md)、
[数据来源与许可](evals/LICENSES.md) 和 [本次发布报告](evals/reports/v1.2.0/RESULTS.md)。
功能测试通过、模型评分、独立人工验收是不同证据，不应混写为回答准确率。
