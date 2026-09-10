"""问答与会话路由：RAG 问答 / 会话列表 / 会话详情 / 删除会话。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    CitationOut,
    ConversationDetailOut,
    ConversationOut,
    MessageOut,
)
from app.services import conversations as conversation_service
from app.services import rag as rag_service
from app.services.embedding import EmbeddingService, get_embedding_service
from app.services.llm import LLMError, LLMService, get_llm_service
from app.services.rag import ConversationNotFoundError

router = APIRouter(prefix="/api/v1", tags=["检索与问答"])


def _conversation_out(conv) -> ConversationOut:
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        message_count=len(conv.messages),
    )


@router.post("/chat", response_model=ChatResponse, summary="知识库问答（RAG）")
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    embedder: EmbeddingService = Depends(get_embedding_service),
    llm: LLMService = Depends(get_llm_service),
) -> ChatResponse:
    settings = get_settings()
    try:
        result = rag_service.answer_question(
            db,
            embedder,
            llm,
            question=request.question,
            top_k=request.top_k,
            conversation_id=request.conversation_id,
            history_limit=settings.rag_history_limit,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LLMError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"LLM 调用失败：{exc}") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=f"问题向量化失败：{exc}") from exc

    citations = [
        CitationOut.model_validate(d) for d in rag_service.citation_dicts(result.citations)
    ]
    return ChatResponse(
        conversation_id=result.conversation.id,
        answer=result.answer,
        citations=citations,
        llm_mode=getattr(llm, "mode", "unknown"),
    )


@router.get("/conversations", response_model=list[ConversationOut], summary="会话列表")
def list_conversations(db: Session = Depends(get_db)) -> list[ConversationOut]:
    convs = conversation_service.list_conversations(db)
    return [_conversation_out(c) for c in convs]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailOut,
    summary="会话详情（含消息与引用）",
)
def get_conversation(
    conversation_id: int, db: Session = Depends(get_db)
) -> ConversationDetailOut:
    conv = conversation_service.get_conversation(db, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ConversationDetailOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        message_count=len(conv.messages),
        messages=[MessageOut.model_validate(m) for m in conv.messages],
    )


@router.delete("/conversations/{conversation_id}", status_code=204, summary="删除会话")
def delete_conversation(
    conversation_id: int, db: Session = Depends(get_db)
) -> None:
    if not conversation_service.delete_conversation(db, conversation_id):
        raise HTTPException(status_code=404, detail="会话不存在")
