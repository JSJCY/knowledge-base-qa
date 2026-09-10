"""RAG 问答编排：检索 → 组装提示词 → 调用 LLM → 持久化会话。"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import Conversation, Message
from app.services.embedding import EmbeddingService
from app.services.llm import LLMService
from app.services.retrieval import RetrievedChunk, search_chunks

SYSTEM_PROMPT_TEMPLATE = """你是知识库问答助手。请仅依据下面的资料回答问题：
- 资料不足以回答时，明确说明「知识库中未找到相关信息」，不要编造。
- 使用与问题相同的语言回答，保持简洁准确。

资料：
{context}"""

NO_CONTEXT = "（知识库为空或未检索到相关内容）"


class ConversationNotFoundError(ValueError):
    pass


@dataclass
class QAResult:
    answer: str
    citations: list[RetrievedChunk]
    conversation: Conversation


def build_context(results: list[RetrievedChunk]) -> str:
    if not results:
        return NO_CONTEXT
    blocks = [
        f"[{i}] 来源：{r.document.filename}（第 {r.chunk.chunk_index} 段）\n{r.chunk.content}"
        for i, r in enumerate(results, start=1)
    ]
    return "\n\n".join(blocks)


def citation_dicts(results: list[RetrievedChunk]) -> list[dict]:
    return [
        {
            "document_id": r.document.id,
            "document_filename": r.document.filename,
            "chunk_index": r.chunk.chunk_index,
            "content": r.chunk.content,
            "score": round(r.score, 6),
        }
        for r in results
    ]


def answer_question(
    db: Session,
    embedder: EmbeddingService,
    llm: LLMService,
    *,
    question: str,
    top_k: int = 5,
    conversation_id: int | None = None,
    history_limit: int = 10,
) -> QAResult:
    """执行一次 RAG 问答并把问答对写入会话。"""
    query_vector = embedder.embed([question])[0]
    results = search_chunks(db, query_vector, top_k=top_k)

    if conversation_id is not None:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(f"会话不存在：{conversation_id}")
    else:
        conversation = Conversation(title=question[:50])
        db.add(conversation)
        db.flush()

    history = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.id.desc())
            .limit(history_limit)
        )
    )[::-1]

    system_content = SYSTEM_PROMPT_TEMPLATE.format(context=build_context(results))
    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
    messages.extend({"role": m.role, "content": m.content} for m in history)
    messages.append({"role": "user", "content": question})

    answer = llm.chat(messages)  # 可能抛 LLMError，由路由层转 502

    db.add(Message(conversation_id=conversation.id, role="user", content=question))
    db.add(
        Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            citations=citation_dicts(results),
        )
    )
    db.commit()
    db.refresh(conversation)
    return QAResult(answer=answer, citations=results, conversation=conversation)
