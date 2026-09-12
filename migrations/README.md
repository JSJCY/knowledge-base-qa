# 数据库迁移

项目在开发环境仍会用 `Base.metadata.create_all()` 自动创建新表；生产环境建议安装 Alembic 后执行迁移：

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

首次迁移应纳入现有 `documents`、`chunks`、`conversations`、`messages` 和 `processing_tasks` 表。
