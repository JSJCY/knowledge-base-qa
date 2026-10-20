from sqlalchemy import create_engine, inspect

from app.core import db


def test_sqlite_upgrade_adds_quality_to_existing_messages(monkeypatch):
    engine=create_engine("sqlite://")
    with engine.begin() as connection:
        for name in ["documents","conversations","messages"]:
            connection.exec_driver_sql(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)")
    monkeypatch.setattr(db,"engine",engine)
    db._add_sqlite_columns()
    assert "quality" in {column["name"] for column in inspect(engine).get_columns("messages")}
    db._add_sqlite_columns()
    engine.dispose()
