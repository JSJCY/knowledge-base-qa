"""文档服务层：上传入库、查询、删除。"""

import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Chunk, Document
from app.services.chunking import split_text
from app.services.embedding import EmbeddingService, vec_to_bytes
from app.services.parsing import parse_bytes


class FileTooLargeError(ValueError):
    def __init__(self, max_mb: int) -> None:
        super().__init__(f"文件过大，上限为 {max_mb} MB")
        self.max_mb = max_mb


def create_document_from_upload(
    db: Session, upload: UploadFile, embedder: EmbeddingService
) -> Document:
    """解析上传文件 → 切块 → 向量化 → 原文落盘 → 写入数据库。"""
    settings = get_settings()
    filename = upload.filename or "unnamed"
    extension = Path(filename).suffix.lower()
    data = upload.file.read()

    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise FileTooLargeError(settings.max_upload_mb)

    text = parse_bytes(data, extension)
    chunk_texts = split_text(text, settings.chunk_size, settings.chunk_overlap)
    embeddings = embedder.embed(chunk_texts)
    storage_path = _store_original(Path(settings.upload_dir), extension, data)

    document = Document(
        filename=filename,
        extension=extension,
        size_bytes=len(data),
        chunk_count=len(chunk_texts),
        storage_path=str(storage_path),
        status="indexed",
    )
    db.add(document)
    db.flush()
    for index, (content, vector) in enumerate(zip(chunk_texts, embeddings, strict=True)):
        db.add(
            Chunk(
                document_id=document.id,
                chunk_index=index,
                content=content,
                embedding=vec_to_bytes(vector),
            )
        )
    db.commit()
    db.refresh(document)
    return document


def _store_original(upload_dir: Path, extension: str, data: bytes) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / f"{uuid.uuid4().hex}{extension}"
    target.write_bytes(data)
    return target


def list_documents(db: Session, *, skip: int = 0, limit: int = 20) -> tuple[int, list[Document]]:
    total = db.scalar(select(func.count(Document.id))) or 0
    items = list(
        db.scalars(
            select(Document)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .offset(skip)
            .limit(limit)
        )
    )
    return total, items


def get_document(db: Session, document_id: int) -> Document | None:
    return db.get(Document, document_id)


def list_chunks(db: Session, document_id: int) -> list[Chunk]:
    return list(
        db.scalars(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
    )


def delete_document(db: Session, document_id: int) -> bool:
    document = db.get(Document, document_id)
    if document is None:
        return False
    if document.storage_path:
        Path(document.storage_path).unlink(missing_ok=True)
    db.delete(document)
    db.commit()
    return True


def reindex_document(db: Session, document_id: int, embedder: EmbeddingService) -> Document | None:
    """重新向量化文档的全部切块（文档不存在时返回 None）。"""
    document = db.get(Document, document_id)
    if document is None:
        return None
    chunks = list_chunks(db, document_id)
    embeddings = embedder.embed([chunk.content for chunk in chunks])
    for chunk, vector in zip(chunks, embeddings, strict=True):
        chunk.embedding = vec_to_bytes(vector)
    document.status = "indexed"
    db.commit()
    db.refresh(document)
    return document
