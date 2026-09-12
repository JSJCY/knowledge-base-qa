"""问答与会话接口的 Pydantic 模式。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"question": "如何启动这个项目？", "top_k": 5}]}
    )

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
    feedback: str | None = None

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


class ConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class MessageFeedbackRequest(BaseModel):
    feedback: str = Field(pattern=r"^(up|down)$")


class AdminOverviewOut(BaseModel):
    document_count: int
    indexed_document_count: int
    conversation_count: int
    message_count: int
    feedback_up_count: int
    feedback_down_count: int
