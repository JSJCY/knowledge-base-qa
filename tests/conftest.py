import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("UPLOAD_DIR", "data/test_uploads")

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import create_app
from app.services.embedding import get_embedding_service
from app.services.llm import get_llm_service
from tests.fakes import FakeEmbeddingService, FakeLLMService

_TEST_UPLOAD_DIR = Path(os.environ["UPLOAD_DIR"])


@pytest.fixture(autouse=True)
def _clean_upload_dir():
    shutil.rmtree(_TEST_UPLOAD_DIR, ignore_errors=True)
    yield
    shutil.rmtree(_TEST_UPLOAD_DIR, ignore_errors=True)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def fake_embedder() -> FakeEmbeddingService:
    return FakeEmbeddingService()


@pytest.fixture()
def fake_llm() -> FakeLLMService:
    return FakeLLMService()


@pytest.fixture()
def client(db_session, fake_embedder, fake_llm) -> TestClient:
    application = create_app()

    def override_get_db():
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_embedding_service] = lambda: fake_embedder
    application.dependency_overrides[get_llm_service] = lambda: fake_llm
    return TestClient(application)
