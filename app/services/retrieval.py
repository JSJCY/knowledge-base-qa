"""向量检索：归一化向量的暴力余弦相似度（点积即余弦）。

小规模知识库（数千块以内）性能足够；更大规模可替换为专用向量库。
"""

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Chunk, Document
from app.services.embedding import bytes_to_vec


@dataclass
class RetrievedChunk:
    chunk: Chunk
    document: Document
    score: float


def search_chunks(
    db: Session,
    query_vector: list[float],
    *,
    top_k: int = 5,
    document_id: int | None = None,
) -> list[RetrievedChunk]:
    """按余弦相似度返回最相关的切块（跳过尚未向量化的块）。"""
    stmt = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.embedding.is_not(None))
    )
    if document_id is not None:
        stmt = stmt.where(Chunk.document_id == document_id)
    rows = db.execute(stmt).all()
    if not rows:
        return []

    matrix = np.stack([bytes_to_vec(chunk.embedding) for chunk, _ in rows])
    query = np.asarray(query_vector, dtype=np.float32)
    scores = matrix @ query

    order = np.argsort(scores)[::-1][:top_k]
    return [
        RetrievedChunk(chunk=rows[i][0], document=rows[i][1], score=float(scores[i]))
        for i in order
    ]
