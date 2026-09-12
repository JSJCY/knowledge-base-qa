"""会话查询与删除。"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.chat import Conversation, Message


def _owner_filter(owner_id: int | None):
    if owner_id is None:
        return Conversation.owner_id.is_(None)
    return Conversation.owner_id == owner_id


def list_conversations(db: Session, owner_id: int | None = None) -> list[Conversation]:
    stmt = select(Conversation).order_by(
        Conversation.created_at.desc(), Conversation.id.desc()
    ).where(_owner_filter(owner_id))
    return list(db.scalars(stmt))


def search_conversations(db: Session, query: str, owner_id: int | None = None) -> list[Conversation]:
    pattern = f"%{query.strip()}%"
    stmt = (
        select(Conversation)
        .join(Message, Message.conversation_id == Conversation.id, isouter=True)
        .where(_owner_filter(owner_id), or_(Conversation.title.ilike(pattern), Message.content.ilike(pattern)))
        .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        .distinct()
    )
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


def rename_conversation(
    db: Session, conversation_id: int, title: str, owner_id: int | None = None
) -> Conversation | None:
    conversation = get_conversation(db, conversation_id, owner_id)
    if conversation is None:
        return None
    conversation.title = title.strip()
    db.commit()
    db.refresh(conversation)
    return conversation


def set_feedback(
    db: Session, conversation_id: int, message_id: int, feedback: str, owner_id: int | None = None
) -> Message | None:
    conversation = get_conversation(db, conversation_id, owner_id)
    if conversation is None:
        return None
    message = db.scalar(
        select(Message).where(Message.id == message_id, Message.conversation_id == conversation.id)
    )
    if message is None or message.role != "assistant":
        return None
    message.feedback = feedback
    db.commit()
    db.refresh(message)
    return message
