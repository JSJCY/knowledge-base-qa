"""问答与会话路由：RAG 问答 / 会话列表 / 会话详情 / 删除会话。"""

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    CitationOut,
    ConversationDetailOut,
    ConversationOut,
    ConversationRenameRequest,
    MessageFeedbackRequest,
    MessageOut,
)
from app.services import conversations as conversation_service
from app.services import rag as rag_service
from app.services.auth import current_user
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
    user: User | None = Depends(current_user),
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
            history_char_budget=settings.rag_history_char_budget,
            query_rewrite_enabled=settings.rag_query_rewrite_enabled,
            candidate_multiplier=settings.rag_candidate_multiplier,
            vector_weight=settings.rag_vector_weight,
            keyword_weight=settings.rag_keyword_weight,
            min_relevance_score=settings.rag_min_relevance_score,
            owner_id=user.id if user else None,
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
        quality=result.quality,
        citations=citations,
        llm_mode=getattr(llm, "mode", "unknown"),
    )


@router.post("/chat/stream", summary="知识库问答（SSE 流式）")
def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    embedder: EmbeddingService = Depends(get_embedding_service),
    llm: LLMService = Depends(get_llm_service),
    user: User | None = Depends(current_user),
) -> StreamingResponse:
    settings = get_settings()

    def events() -> Iterator[str]:
        try:
            preparation = None
            for part, _preparation in rag_service.stream_answer_question(
                db, embedder, llm, question=request.question, top_k=request.top_k,
                conversation_id=request.conversation_id, history_limit=settings.rag_history_limit,
                history_char_budget=settings.rag_history_char_budget,
                query_rewrite_enabled=settings.rag_query_rewrite_enabled,
                candidate_multiplier=settings.rag_candidate_multiplier,
                vector_weight=settings.rag_vector_weight,
                keyword_weight=settings.rag_keyword_weight,
                min_relevance_score=settings.rag_min_relevance_score,
                owner_id=user.id if user else None,
            ):
                preparation = _preparation
                yield f"event: delta\ndata: {json.dumps({'content': part}, ensure_ascii=False)}\n\n"
            assert preparation is not None
            payload = {"conversation_id": preparation.conversation.id,
                       "citations": rag_service.citation_dicts(preparation.citations),
                       "llm_mode": getattr(llm, "mode", "unknown"),
                       "quality":preparation.quality}
            yield f"event: done\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except ConversationNotFoundError as exc:
            db.rollback()
            yield f"event: error\ndata: {json.dumps({'detail': str(exc)}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            db.rollback()
            detail = json.dumps({"detail": f"问答失败：{exc}"}, ensure_ascii=False)
            yield f"event: error\ndata: {detail}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/conversations", response_model=list[ConversationOut], summary="会话列表")
def list_conversations(
    q: str | None = Query(None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[ConversationOut]:
    owner_id = user.id if user else None
    convs = conversation_service.search_conversations(db, q, owner_id) if q else conversation_service.list_conversations(db, owner_id)
    return [_conversation_out(c) for c in convs]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailOut,
    summary="会话详情（含消息与引用）",
)
def get_conversation(
    conversation_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> ConversationDetailOut:
    conv = conversation_service.get_conversation(db, conversation_id, user.id if user else None)
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
    conversation_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> None:
    if not conversation_service.delete_conversation(db, conversation_id, user.id if user else None):
        raise HTTPException(status_code=404, detail="会话不存在")


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut, summary="重命名会话")
def rename_conversation(
    conversation_id: int,
    request: ConversationRenameRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> ConversationOut:
    conversation = conversation_service.rename_conversation(
        db, conversation_id, request.title, user.id if user else None
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return _conversation_out(conversation)


@router.post("/conversations/{conversation_id}/messages/{message_id}/feedback", response_model=MessageOut, summary="提交回答反馈")
def message_feedback(
    conversation_id: int,
    message_id: int,
    request: MessageFeedbackRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> MessageOut:
    message = conversation_service.set_feedback(
        db, conversation_id, message_id, request.feedback, user.id if user else None
    )
    if message is None:
        raise HTTPException(status_code=404, detail="回答或会话不存在")
    return MessageOut.model_validate(message)


@router.get("/conversations/{conversation_id}/export", response_class=PlainTextResponse, summary="导出会话 Markdown")
def export_conversation(
    conversation_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> PlainTextResponse:
    conversation = conversation_service.get_conversation(db, conversation_id, user.id if user else None)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    lines = [f"# {conversation.title}\n"]
    for message in conversation.messages:
        label = "用户" if message.role == "user" else "助手"
        lines.extend([f"## {label}\n", message.content, ""])
    return PlainTextResponse("\n".join(lines), headers={"Content-Disposition": f'attachment; filename="conversation-{conversation_id}.md"'})
