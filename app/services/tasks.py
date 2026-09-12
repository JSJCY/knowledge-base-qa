"""进程内后台任务队列：适合单实例部署，任务状态持久化到数据库。"""

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.task import ProcessingTask
from app.services.documents import index_pending_document, reindex_document
from app.services.embedding import get_embedding_service

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kb-worker")


def create_task(db: Session, *, kind: str, document_id: int) -> ProcessingTask:
    task = ProcessingTask(kind=kind, document_id=document_id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: str) -> ProcessingTask | None:
    return db.get(ProcessingTask, task_id)


def enqueue(task_id: str) -> None:
    _executor.submit(_run_task, task_id)


def recover_pending_tasks() -> None:
    """服务重启后重新入队未完成任务，避免容器重启造成任务永久卡住。"""
    db = SessionLocal()
    try:
        tasks = list(
            db.scalars(
                select(ProcessingTask).where(ProcessingTask.status.in_(("queued", "running")))
            )
        )
        for task in tasks:
            task.status = "queued"
        db.commit()
        for task in tasks:
            enqueue(task.id)
    finally:
        db.close()


def _run_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        task = db.get(ProcessingTask, task_id)
        if task is None:
            return
        task.status = "running"
        task.progress = 10
        db.commit()
        embedder = get_embedding_service()
        if task.kind == "index":
            index_pending_document(db, task.document_id, embedder)
        elif task.kind == "reindex":
            document = reindex_document(db, task.document_id, embedder)
            if document is None:
                raise ValueError("文档不存在")
        else:
            raise ValueError(f"未知任务类型：{task.kind}")
        task = db.get(ProcessingTask, task_id)
        if task:
            task.status = "completed"
            task.progress = 100
            db.commit()
    except Exception as exc:
        db.rollback()
        task = db.get(ProcessingTask, task_id)
        if task:
            task.status = "failed"
            task.error = str(exc)[:1000]
            db.commit()
    finally:
        db.close()
