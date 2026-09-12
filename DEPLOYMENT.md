# 生产部署指南

本指南适用于单台 Linux 云服务器。当前架构使用 SQLite、持久化 Docker Volume 和进程内后台任务队列，因此**只能运行一个 `kb-qa` 应用副本**。

## 服务器准备

- Ubuntu 22.04 / 24.04
- 建议至少 2 核 CPU、4 GB 内存、40 GB SSD
- 已安装 Docker Engine 和 Docker Compose Plugin
- 域名 A/AAAA 记录已指向服务器公网 IP
- 防火墙放行 TCP 80、443；不要对公网暴露 8000 端口

## 部署步骤

```bash
git clone <你的仓库地址> kb-qa
cd kb-qa
cp .env.example .env
```

编辑 `.env`，至少配置：

```ini
DOMAIN=kb.example.com
DEEPSEEK_API_KEY=你的密钥
DEBUG=false
AUTH_ENABLED=true
RAG_QUERY_REWRITE_ENABLED=false
```

如需 API 级别访问控制，可同时配置随机值：

```ini
API_KEY=请替换为足够长的随机字符串
```

启动生产服务：

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

Caddy 会在域名解析生效且 80/443 端口可访问时自动申请并续期 HTTPS 证书。完成后访问：

```text
https://kb.example.com/
https://kb.example.com/docs
https://kb.example.com/health
```

## 更新与回滚

更新代码：

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

回滚到指定提交：

```bash
git checkout <commit-id>
docker compose -f docker-compose.prod.yml up -d --build
```

## 数据备份

应用数据保存在 Docker Volume `kb_data`，其中包括 SQLite 数据库和原始上传文件。更新镜像不会删除该 Volume。

建议定期备份：

```bash
docker run --rm -v fastapi_kb_data:/data -v "$PWD":/backup alpine tar czf /backup/kb-data-backup.tgz /data
```

恢复前先停止服务，再将备份解压回同一个 Volume。生产环境应把备份文件同步至另一台机器或对象存储。

## 运维说明

- 容器重启后，状态为 `queued` 或 `running` 的索引任务会重新入队。
- 首次向量化会下载模型，需确保服务器能访问模型源；国内网络可设置 `HF_ENDPOINT=https://hf-mirror.com`。
- Caddy 负责 HTTPS 和 SSE 流式转发，配置中已经关闭代理缓冲。
- 后续扩展到多实例时，应迁移至 PostgreSQL、Redis 队列、对象存储和专用向量数据库。
