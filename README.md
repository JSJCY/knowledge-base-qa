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
| 1 | 项目骨架：配置管理、健康检查、测试与 CI | 🚧 进行中 |
| 2 | 文档管理：上传 / 解析 / 切块 / 存储 | ⬜ 未开始 |
| 3 | 向量化与检索：embedding + 相似度搜索 | ⬜ 未开始 |
| 4 | RAG 问答：DeepSeek 接入、引用来源、会话历史 | ⬜ 未开始 |
| 5 | 交付收尾：文档、覆盖率、v1.0.0 发布 | ⬜ 未开始 |

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
