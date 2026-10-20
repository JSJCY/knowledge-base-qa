"""向量检索：归一化向量的暴力余弦相似度（点积即余弦）。

小规模知识库（数千块以内）性能足够；更大规模可替换为专用向量库。
"""

import re
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


_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> set[str]:
    """提取适用于中英文混合文本的轻量关键词集合。"""
    return set(_TOKEN_PATTERN.findall(text.lower()))


def keyword_score(query_tokens: set[str], content: str) -> float:
    """词面命中可补足语义向量对专有名词的不足。"""
    content_tokens = tokenize(content)
    if not query_tokens or not content_tokens:
        return 0.0
    return 2 * len(query_tokens & content_tokens) / (len(query_tokens) + len(content_tokens))


def search_chunks(
    db: Session,
    query_vector: list[float],
    *,
    top_k: int = 5,
    document_id: int | None = None,
    keyword_query: str | None = None,
    candidate_multiplier: int = 3,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
    owner_id: int | None = None,
) -> list[RetrievedChunk]:
    """混合召回并重排序：向量语义 + 关键词命中（跳过未向量化切块）。"""
    stmt = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.embedding.is_not(None), Document.deleted_at.is_(None))
        .where(Document.owner_id.is_(None) if owner_id is None else Document.owner_id == owner_id)
    )
    if document_id is not None:
        stmt = stmt.where(Chunk.document_id == document_id)
    rows = db.execute(stmt).all()
    if not rows:
        return []

    matrix = np.stack([bytes_to_vec(chunk.embedding) for chunk, _ in rows])
    query = np.asarray(query_vector, dtype=np.float32)
    vector_scores = matrix @ query
    query_tokens = tokenize(keyword_query or "")
    keyword_scores = np.asarray(
        [keyword_score(query_tokens, chunk.content) for chunk, _ in rows], dtype=np.float32
    )
    candidate_count = min(len(rows), max(top_k, top_k * candidate_multiplier))
    vector_order = np.argsort(vector_scores)[::-1][:candidate_count]
    keyword_order = np.argsort(keyword_scores)[::-1][:candidate_count]
    candidate_indices = set(vector_order.tolist()) | set(keyword_order.tolist())
    semantic_scores = np.clip(vector_scores, 0, 1)
    combined_scores = vector_weight * semantic_scores + keyword_weight * keyword_scores
    order = sorted(
        candidate_indices, key=lambda index: combined_scores[index], reverse=True
    )[:top_k]
    return [
        RetrievedChunk(chunk=rows[i][0], document=rows[i][1], score=float(combined_scores[i]))
        for i in order
    ]
