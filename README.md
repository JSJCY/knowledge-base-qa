# 知识库问答系统（Knowledge Base QA）

[![CI](https://github.com/JSJCY/knowledge-base-qa/actions/workflows/ci.yml/badge.svg)](https://github.com/JSJCY/knowledge-base-qa/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![Coverage](https://img.shields.io/badge/coverage-92%25-brightgreen)](#)
[![Release](https://img.shields.io/github/v/release/JSJCY/knowledge-base-qa)](https://github.com/JSJCY/knowledge-base-qa/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

基于 **FastAPI + 本地向量检索（RAG）+ DeepSeek** 的知识库问答系统：

> 上传文档（.txt / .md / .pdf）→ 自动解析切块 → **本地向量化**（BGE 中文模型，免费离线）→ 提问时检索最相关内容 → **DeepSeek 生成带引用来源的回答**，支持多轮会话上下文。

## ✨ 特性

- 📄 **文档管理**：上传 / 列表 / 详情 / 切块查看 / 删除；支持 TXT、Markdown、PDF，兼容 UTF-8 与 GB18030 中文编码
- 🧩 **智能切块**：段落感知打包 + 超长段落窗口硬切 + 块间重叠，兼顾语义完整与检索粒度
- 🧠 **本地向量化**：fastembed + `BAAI/bge-small-zh-v1.5`（ONNX 本地推理，无需付费 embedding API，模型仅首次下载）
- 🔍 **语义检索**：余弦相似度排序，支持全库检索或限定单文档，返回相关度分数
- 💬 **RAG 问答**：DeepSeek 严格依据检索资料作答，资料不足时诚实拒答不编造；回答自动附带引用来源（文档名 / 段落号 / 相似度）
- 🗂 **多轮会话**：会话与消息持久化（SQLite），自动生成会话标题，追问自动携带上下文
- 🔌 **可插拔设计**：向量化与 LLM 均为依赖注入；未配置 API Key 时自动降级 Mock 模式，全流程仍可跑通
- ✅ **工程化**：50 个 pytest 用例、92% 覆盖率、ruff 代码规范、GitHub Actions CI、Swagger 交互文档

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
| GET | `/health` | 健康检查 |
| GET | `/` | 服务信息（版本、LLM 是否启用） |
| POST | `/api/v1/documents/upload` | 上传文档（.txt / .md / .pdf，自动解析、切块、向量化） |
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
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | fastembed 向量模型 |
| `HF_ENDPOINT` | 空 | HuggingFace 镜像（国内建议 `https://hf-mirror.com`） |
| `DATABASE_URL` | `sqlite:///./kb.db` | 数据库连接串 |
| `UPLOAD_DIR` | `data/uploads` | 原始文件保存目录 |
| `MAX_UPLOAD_MB` | `20` | 单文件大小上限（MB） |
| `CHUNK_SIZE` | `500` | 切块目标长度（字符） |
| `CHUNK_OVERLAP` | `50` | 相邻切块重叠长度（字符） |
| `DEBUG` | `false` | FastAPI 调试模式 |

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
├── tests/                     # 50 个测试（假向量化器/假 LLM 依赖注入，CI 零外部依赖）
├── .github/workflows/ci.yml   # CI：ruff lint + pytest + coverage
├── pyproject.toml             # 依赖与工具配置
└── .env.example               # 配置模板
```

## 🧪 测试与质量

```bash
pytest --cov=app        # 50 个用例，覆盖率 92%
ruff check .            # 代码规范
```

测试策略：真实向量模型与 DeepSeek API 通过**依赖注入**替换为确定性假实现（词袋假向量器 / 回显假 LLM），因此 CI 无需下载模型、不消耗 API 额度、秒级完成；真实模型链路通过本地端到端验收（中文语义检索命中、多轮追问、库外问题拒答均验证通过）。

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

## 📄 License

[MIT](LICENSE) © 2026 JSJCY
