# 知识库问答系统（Knowledge Base QA）

基于 **FastAPI + 向量检索 RAG + DeepSeek** 的知识库问答系统：上传文档 → 切块向量化 → 提问时检索相关内容并由大模型生成带引用来源的回答。

> 项目按阶段开发中，当前进度见下方路线图。

## 技术栈

- **Web 框架**：FastAPI（自带 Swagger 交互文档 `/docs`）
- **存储**：SQLite + SQLAlchemy
- **检索**：fastembed 本地向量化（BGE 中文模型）+ 余弦相似度
- **大模型**：DeepSeek Chat API（可插拔，未配置 Key 时自动使用 Mock 模式）
- **质量保障**：pytest + ruff + GitHub Actions CI

## 开发路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| 1 | 项目骨架：配置管理、健康检查、测试与 CI | ✅ 完成 |
| 2 | 文档管理：上传 / 解析 / 切块 / 存储 | ✅ 完成 |
| 3 | 向量化与检索：embedding + 相似度搜索 | ✅ 完成 |
| 4 | RAG 问答：DeepSeek 接入、引用来源、会话历史 | 🚧 进行中 |
| 5 | 交付收尾：文档、覆盖率、v1.0.0 发布 | ⬜ 未开始 |

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/` | 服务信息 |
| POST | `/api/v1/documents/upload` | 上传文档（.txt / .md / .pdf，自动解析并切块） |
| GET | `/api/v1/documents` | 文档列表（分页） |
| GET | `/api/v1/documents/{id}` | 文档详情 |
| GET | `/api/v1/documents/{id}/chunks` | 文档切块列表 |
| DELETE | `/api/v1/documents/{id}` | 删除文档及其切块 |
| POST | `/api/v1/documents/{id}/reindex` | 重新向量化文档 |
| POST | `/api/v1/search` | 向量检索（余弦相似度排序，返回最相关切块） |

> 首次上传/检索会自动下载本地向量模型（`BAAI/bge-small-zh-v1.5`，约 100MB，实测约 1 分钟），之后全部走本地缓存，无需联网。国内网络建议在 `.env` 中设置 `HF_ENDPOINT=https://hf-mirror.com`。

## 快速开始（阶段 1）

```bash
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"   # Windows
cp .env.example .env                     # 按需填写配置
.venv\Scripts\uvicorn app.main:app --reload
```

- 健康检查：http://127.0.0.1:8000/health
- Swagger 文档：http://127.0.0.1:8000/docs

## 测试

```bash
pytest
ruff check .
```
