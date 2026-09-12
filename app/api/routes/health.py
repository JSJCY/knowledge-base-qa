"""系统级路由：健康检查与服务信息。"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.chat import Conversation, Message
from app.models.document import Document
from app.models.user import User
from app.schemas.chat import AdminOverviewOut
from app.services.auth import current_user

router = APIRouter(tags=["系统"])


@router.get("/health", summary="健康检查")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/info", summary="服务信息")
def service_info() -> dict[str, object]:
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "llm_enabled": settings.llm_enabled,
    }


@router.get("/api/v1/admin/overview", response_model=AdminOverviewOut, summary="管理概览")
def admin_overview(
    db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> AdminOverviewOut:
    owner_filter = Document.owner_id.is_(None) if user is None else Document.owner_id == user.id
    conversation_filter = Conversation.owner_id.is_(None) if user is None else Conversation.owner_id == user.id
    document_count = db.scalar(select(func.count(Document.id)).where(owner_filter, Document.deleted_at.is_(None))) or 0
    indexed_count = db.scalar(select(func.count(Document.id)).where(owner_filter, Document.status == "indexed", Document.deleted_at.is_(None))) or 0
    conversation_count = db.scalar(select(func.count(Conversation.id)).where(conversation_filter)) or 0
    message_count = db.scalar(select(func.count(Message.id)).join(Conversation).where(conversation_filter)) or 0
    up_count = db.scalar(select(func.count(Message.id)).join(Conversation).where(conversation_filter, Message.feedback == "up")) or 0
    down_count = db.scalar(select(func.count(Message.id)).join(Conversation).where(conversation_filter, Message.feedback == "down")) or 0
    return AdminOverviewOut(document_count=document_count, indexed_document_count=indexed_count, conversation_count=conversation_count, message_count=message_count, feedback_up_count=up_count, feedback_down_count=down_count)
