"""检索路由：向量相似度搜索。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.search import SearchRequest, SearchResponse, SearchResultOut
from app.services.embedding import EmbeddingService, get_embedding_service
from app.services.retrieval import search_chunks

router = APIRouter(prefix="/api/v1", tags=["检索与问答"])


@router.post("/search", response_model=SearchResponse, summary="向量检索")
def search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    embedder: EmbeddingService = Depends(get_embedding_service),
) -> SearchResponse:
    try:
        query_vector = embedder.embed([request.query])[0]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"查询向量化失败：{exc}") from exc

    results = search_chunks(
        db,
        query_vector,
        top_k=request.top_k,
        document_id=request.document_id,
    )
    return SearchResponse(
        query=request.query,
        count=len(results),
        results=[
            SearchResultOut(
                chunk_id=r.chunk.id,
                document_id=r.document.id,
                document_filename=r.document.filename,
                chunk_index=r.chunk.chunk_index,
                content=r.chunk.content,
                score=round(r.score, 6),
            )
            for r in results
        ],
    )
