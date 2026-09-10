from fpdf import FPDF

UPLOAD_URL = "/api/v1/documents/upload"


def _upload(client, filename: str, content: bytes):
    return client.post(
        UPLOAD_URL,
        files={"file": (filename, content, "application/octet-stream")},
    )


def _make_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=14)
    pdf.cell(text=text, w=0, h=10)
    return bytes(pdf.output())


def test_upload_txt(client):
    resp = _upload(client, "笔记.txt", "第一段内容。\n\n第二段内容。".encode())
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "笔记.txt"
    assert body["extension"] == ".txt"
    assert body["status"] == "uploaded"
    assert body["chunk_count"] >= 1
    assert body["size_bytes"] > 0


def test_upload_md_and_read_chunks(client):
    resp = _upload(client, "readme.md", "# 标题\n\n这是正文段落。".encode())
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    chunks = client.get(f"/api/v1/documents/{doc_id}/chunks")
    assert chunks.status_code == 200
    items = chunks.json()
    assert items[0]["chunk_index"] == 0
    assert "正文段落" in items[0]["content"]


def test_upload_pdf(client):
    resp = _upload(client, "report.pdf", _make_pdf("quarterly knowledge base report"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["extension"] == ".pdf"
    assert body["chunk_count"] >= 1


def test_upload_unsupported_type(client):
    resp = _upload(client, "virus.exe", b"MZ...")
    assert resp.status_code == 415


def test_upload_empty_file(client):
    resp = _upload(client, "empty.txt", b"")
    assert resp.status_code == 422


def test_list_and_pagination(client):
    for i in range(3):
        assert _upload(client, f"doc{i}.txt", f"content {i}".encode()).status_code == 201

    page = client.get("/api/v1/documents", params={"skip": 0, "limit": 2})
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2

    rest = client.get("/api/v1/documents", params={"skip": 2, "limit": 2})
    assert len(rest.json()["items"]) == 1


def test_get_document_detail_and_404(client):
    doc_id = _upload(client, "a.txt", b"hello").json()["id"]

    ok = client.get(f"/api/v1/documents/{doc_id}")
    assert ok.status_code == 200
    assert ok.json()["id"] == doc_id

    missing = client.get("/api/v1/documents/99999")
    assert missing.status_code == 404

    missing_chunks = client.get("/api/v1/documents/99999/chunks")
    assert missing_chunks.status_code == 404


def test_delete_document(client, db_session):
    from app.models.document import Chunk

    doc_id = _upload(client, "del.txt", b"to be deleted").json()["id"]

    resp = client.delete(f"/api/v1/documents/{doc_id}")
    assert resp.status_code == 204

    assert client.get(f"/api/v1/documents/{doc_id}").status_code == 404
    assert db_session.query(Chunk).filter_by(document_id=doc_id).count() == 0
    assert client.delete(f"/api/v1/documents/{doc_id}").status_code == 404


def test_upload_size_limit(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    resp = _upload(client, "big.txt", b"x" * 1024)
    assert resp.status_code == 413
