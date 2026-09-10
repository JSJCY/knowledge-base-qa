DOC_WEB = (
    "FastAPI is a modern Python web framework for building APIs. "
    "FastAPI web framework provides high performance and automatic docs."
)
DOC_VECTOR = (
    "Vector search stores embeddings for similarity retrieval. "
    "Cosine similarity measures how relevant two vectors are."
)


def _upload(client, filename: str, text: str):
    return client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, text.encode("utf-8"), "text/plain")},
    )


def _upload_two_docs(client):
    a = _upload(client, "web.txt", DOC_WEB)
    b = _upload(client, "vector.txt", DOC_VECTOR)
    assert a.status_code == 201
    assert b.status_code == 201
    return a.json()["id"], b.json()["id"]


def test_search_finds_relevant_document(client):
    _upload_two_docs(client)
    resp = client.post("/api/v1/search", json={"query": "Python web framework FastAPI", "top_k": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    assert body["results"][0]["document_filename"] == "web.txt"
    assert body["results"][0]["score"] > 0
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)


def test_search_respects_top_k(client):
    _upload_two_docs(client)
    resp = client.post("/api/v1/search", json={"query": "similarity vector embeddings", "top_k": 1})
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 1


def test_search_filters_by_document(client):
    _, doc_b = _upload_two_docs(client)
    resp = client.post(
        "/api/v1/search",
        json={"query": "FastAPI web framework", "top_k": 10, "document_id": doc_b},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert results
    assert all(r["document_id"] == doc_b for r in results)


def test_search_empty_query_rejected(client):
    resp = client.post("/api/v1/search", json={"query": "", "top_k": 5})
    assert resp.status_code == 422


def test_search_on_empty_kb(client):
    resp = client.post("/api/v1/search", json={"query": "anything"})
    assert resp.status_code == 200
    assert resp.json() == {"query": "anything", "count": 0, "results": []}


def test_reindex_restores_missing_embeddings(client, db_session):
    from app.models.document import Chunk

    doc_id, _ = _upload_two_docs(client)

    # 人为清空该文档所有切块的向量
    for chunk in db_session.query(Chunk).filter_by(document_id=doc_id):
        chunk.embedding = None
    db_session.commit()

    resp = client.post("/api/v1/search", json={"query": "FastAPI web framework", "top_k": 5})
    assert all(r["document_id"] != doc_id for r in resp.json()["results"])

    reindex = client.post(f"/api/v1/documents/{doc_id}/reindex")
    assert reindex.status_code == 200
    assert reindex.json()["status"] == "indexed"

    resp = client.post("/api/v1/search", json={"query": "FastAPI web framework", "top_k": 5})
    assert resp.json()["results"][0]["document_id"] == doc_id


def test_reindex_missing_document_404(client):
    resp = client.post("/api/v1/documents/99999/reindex")
    assert resp.status_code == 404
