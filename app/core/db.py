"""数据库引擎与会话管理。"""

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


_settings = get_settings()
engine = _make_engine(_settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """建表（先导入模型模块以完成注册）。"""
    from app import models  # noqa: F401

    Base.metadata.create_all(engine)
    if engine.url.get_backend_name() == "sqlite":
        _add_sqlite_columns()


def _add_sqlite_columns() -> None:
    """为开发环境中已有的 SQLite 数据库补齐可空治理字段。"""
    columns = {
        "documents": {
            "owner_id": "INTEGER",
            "content_hash": "VARCHAR(64)",
            "version": "INTEGER DEFAULT 1",
            "deleted_at": "DATETIME",
        },
        "conversations": {"owner_id": "INTEGER"},
        "messages": {"feedback": "VARCHAR(16)", "quality": "JSON"},
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, additions in columns.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in additions.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
