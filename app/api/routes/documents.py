"""文档管理路由：上传 / 列表 / 详情 / 切块 / 删除。"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.document import ChunkOut, DocumentListOut, DocumentOut
from app.services import documents as document_service
from app.services.documents import FileTooLargeError
from app.services.embedding import EmbeddingService, get_embedding_service
from app.services.parsing import EmptyFileError, UnsupportedFileTypeError

router = APIRouter(prefix="/api/v1/documents", tags=["文档管理"])


@router.post("/upload", response_model=DocumentOut, status_code=201, summary="上传文档")
def upload_document(
    file: UploadFile = File(..., description="支持 .txt / .md / .pdf"),
    db: Session = Depends(get_db),
    embedder: EmbeddingService = Depends(get_embedding_service),
) -> DocumentOut:
    try:
        document = document_service.create_document_from_upload(db, file, embedder)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except EmptyFileError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:  # 文件解析失败（如损坏的 PDF）
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # 向量化失败（如模型下载失败）
        db.rollback()
        raise HTTPException(status_code=503, detail=f"向量化失败：{exc}") from exc
    return DocumentOut.model_validate(document)


@router.get("", response_model=DocumentListOut, summary="文档列表")
def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> DocumentListOut:
    total, items = document_service.list_documents(db, skip=skip, limit=limit)
    return DocumentListOut(total=total, items=[DocumentOut.model_validate(d) for d in items])


@router.get("/{document_id}", response_model=DocumentOut, summary="文档详情")
def get_document(document_id: int, db: Session = Depends(get_db)) -> DocumentOut:
    document = document_service.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentOut.model_validate(document)


@router.get("/{document_id}/chunks", response_model=list[ChunkOut], summary="文档切块列表")
def get_document_chunks(document_id: int, db: Session = Depends(get_db)) -> list[ChunkOut]:
    if document_service.get_document(db, document_id) is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    chunks = document_service.list_chunks(db, document_id)
    return [ChunkOut.model_validate(c) for c in chunks]


@router.delete("/{document_id}", status_code=204, summary="删除文档")
def delete_document(document_id: int, db: Session = Depends(get_db)) -> None:
    if not document_service.delete_document(db, document_id):
        raise HTTPException(status_code=404, detail="文档不存在")


@router.post("/{document_id}/reindex", response_model=DocumentOut, summary="重新向量化文档")
def reindex_document(
    document_id: int,
    db: Session = Depends(get_db),
    embedder: EmbeddingService = Depends(get_embedding_service),
) -> DocumentOut:
    try:
        document = document_service.reindex_document(db, document_id, embedder)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=f"向量化失败：{exc}") from exc
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentOut.model_validate(document)
