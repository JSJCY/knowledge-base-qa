"""文档相关接口的 Pydantic 模式。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    chunk_index: int
    content: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    extension: str
    size_bytes: int
    status: str
    chunk_count: int
    created_at: datetime


class DocumentListOut(BaseModel):
    total: int
    items: list[DocumentOut]
