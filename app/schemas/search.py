"""检索接口的 Pydantic 模式。"""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="查询内容")
    top_k: int = Field(5, ge=1, le=50, description="返回的最相关片段数量")
    document_id: int | None = Field(None, description="限定在某个文档内检索（可选）")


class SearchResultOut(BaseModel):
    chunk_id: int
    document_id: int
    document_filename: str
    chunk_index: int
    content: str
    score: float = Field(description="余弦相似度，越大越相关")


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[SearchResultOut]
