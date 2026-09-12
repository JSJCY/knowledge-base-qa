"""文档管理路由：上传 / 列表 / 详情 / 切块 / 删除。"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.user import User
from app.schemas.document import ChunkOut, DocumentListOut, DocumentOut, ProcessingTaskOut
from app.services import documents as document_service
from app.services import tasks as task_service
from app.services.auth import current_user
from app.services.documents import FileTooLargeError
from app.services.embedding import EmbeddingService, get_embedding_service
from app.services.parsing import EmptyFileError, UnsupportedFileTypeError

router = APIRouter(prefix="/api/v1/documents", tags=["文档管理"])


@router.post("/upload", response_model=DocumentOut, status_code=201, summary="上传文档")
def upload_document(
    file: UploadFile = File(..., description="支持 .txt / .md / .pdf"),
    db: Session = Depends(get_db),
    embedder: EmbeddingService = Depends(get_embedding_service),
    user: User | None = Depends(current_user),
) -> DocumentOut:
    try:
        document = document_service.create_document_from_upload(
            db, file, embedder, user.id if user else None
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except EmptyFileError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except document_service.DuplicateDocumentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:  # 文件解析失败（如损坏的 PDF）
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # 向量化失败（如模型下载失败）
        db.rollback()
        raise HTTPException(status_code=503, detail=f"向量化失败：{exc}") from exc
    return DocumentOut.model_validate(document)


@router.post(
    "/upload/async",
    response_model=ProcessingTaskOut,
    status_code=202,
    summary="异步上传并建立索引",
)
def upload_document_async(
    file: UploadFile = File(..., description="支持 .txt / .md / .pdf"),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> ProcessingTaskOut:
    try:
        document = document_service.create_pending_document(db, file, user.id if user else None)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except EmptyFileError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except document_service.DuplicateDocumentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    task = task_service.create_task(db, kind="index", document_id=document.id)
    task_service.enqueue(task.id)
    return ProcessingTaskOut.model_validate(task)


@router.get("", response_model=DocumentListOut, summary="文档列表")
def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> DocumentListOut:
    total, items = document_service.list_documents(
        db, skip=skip, limit=limit, owner_id=user.id if user else None
    )
    return DocumentListOut(total=total, items=[DocumentOut.model_validate(d) for d in items])


@router.get("/tasks/{task_id}", response_model=ProcessingTaskOut, summary="查看后台任务状态")
def get_processing_task(task_id: str, db: Session = Depends(get_db)) -> ProcessingTaskOut:
    task = task_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="后台任务不存在")
    return ProcessingTaskOut.model_validate(task)


@router.get("/{document_id}", response_model=DocumentOut, summary="文档详情")
def get_document(
    document_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> DocumentOut:
    document = document_service.get_document(db, document_id, user.id if user else None)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentOut.model_validate(document)


@router.get("/{document_id}/chunks", response_model=list[ChunkOut], summary="文档切块列表")
def get_document_chunks(
    document_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> list[ChunkOut]:
    if document_service.get_document(db, document_id, user.id if user else None) is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    chunks = document_service.list_chunks(db, document_id)
    return [ChunkOut.model_validate(c) for c in chunks]


@router.delete("/{document_id}", status_code=204, summary="删除文档")
def delete_document(
    document_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> None:
    if not document_service.delete_document(db, document_id, user.id if user else None):
        raise HTTPException(status_code=404, detail="文档不存在")


@router.post("/{document_id}/reindex", response_model=DocumentOut, summary="重新向量化文档")
def reindex_document(
    document_id: int,
    db: Session = Depends(get_db),
    embedder: EmbeddingService = Depends(get_embedding_service),
    user: User | None = Depends(current_user),
) -> DocumentOut:
    if document_service.get_document(db, document_id, user.id if user else None) is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    try:
        document = document_service.reindex_document(db, document_id, embedder)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=f"向量化失败：{exc}") from exc
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentOut.model_validate(document)


@router.post(
    "/{document_id}/reindex/async",
    response_model=ProcessingTaskOut,
    status_code=202,
    summary="异步重新向量化文档",
)
def reindex_document_async(
    document_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> ProcessingTaskOut:
    if document_service.get_document(db, document_id, user.id if user else None) is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    task = task_service.create_task(db, kind="reindex", document_id=document_id)
    task_service.enqueue(task.id)
    return ProcessingTaskOut.model_validate(task)


@router.post("/{document_id}/restore", response_model=DocumentOut, summary="恢复软删除文档")
def restore_document(
    document_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> DocumentOut:
    document = document_service.restore_document(db, document_id, user.id if user else None)
    if document is None:
        raise HTTPException(status_code=404, detail="可恢复文档不存在")
    return DocumentOut.model_validate(document)
