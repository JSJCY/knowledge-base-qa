"""会话查询与删除。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import Conversation


def _owner_filter(owner_id: int | None):
    if owner_id is None:
        return Conversation.owner_id.is_(None)
    return Conversation.owner_id == owner_id


def list_conversations(db: Session, owner_id: int | None = None) -> list[Conversation]:
    stmt = select(Conversation).order_by(
        Conversation.created_at.desc(), Conversation.id.desc()
    ).where(_owner_filter(owner_id))
    return list(db.scalars(stmt))


def get_conversation(
    db: Session, conversation_id: int, owner_id: int | None = None
) -> Conversation | None:
    stmt = select(Conversation).where(Conversation.id == conversation_id, _owner_filter(owner_id))
    return db.scalar(stmt)


def delete_conversation(db: Session, conversation_id: int, owner_id: int | None = None) -> bool:
    conversation = get_conversation(db, conversation_id, owner_id)
    if conversation is None:
        return False
    db.delete(conversation)
    db.commit()
    return True
