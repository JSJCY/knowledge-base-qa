"""会话查询与删除。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import Conversation


def list_conversations(db: Session) -> list[Conversation]:
    stmt = select(Conversation).order_by(
        Conversation.created_at.desc(), Conversation.id.desc()
    )
    return list(db.scalars(stmt))


def get_conversation(db: Session, conversation_id: int) -> Conversation | None:
    return db.get(Conversation, conversation_id)


def delete_conversation(db: Session, conversation_id: int) -> bool:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        return False
    db.delete(conversation)
    db.commit()
    return True
