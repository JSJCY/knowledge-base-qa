"""问答与会话接口的 Pydantic 模式。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000, description="你的问题")
    top_k: int = Field(5, ge=1, le=20, description="检索的最相关片段数量")
    conversation_id: int | None = Field(None, description="传入已有会话 ID 可携带上下文继续提问")


class CitationOut(BaseModel):
    document_id: int
    document_filename: str
    chunk_index: int
    content: str
    score: float


class ChatResponse(BaseModel):
    conversation_id: int
    answer: str
    citations: list[CitationOut]
    llm_mode: str = Field(description="deepseek=真实模型 / mock=未配置 Key / fake=测试")


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    citations: list[CitationOut] = []

    @field_validator("citations", mode="before")
    @classmethod
    def _none_to_list(cls, v):
        return v or []


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    message_count: int = 0


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut] = []
