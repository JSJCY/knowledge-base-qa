from datetime import UTC, datetime

from app.models.document import Chunk, Document
from app.services.embedding import vec_to_bytes
from app.services.retrieval import search_chunks


def test_retrieval_excludes_deleted_and_other_owner_documents(db_session, fake_embedder):
    vector=fake_embedder.embed(["Python"])[0]
    for owner,deleted in [(None,False),(None,True),(999,False)]:
        doc=Document(filename="doc.txt",extension=".txt",owner_id=owner,deleted_at=datetime.now(UTC) if deleted else None)
        db_session.add(doc)
        db_session.flush()
        db_session.add(Chunk(document_id=doc.id,chunk_index=0,content="Python",embedding=vec_to_bytes(vector)))
    db_session.commit()
    results=search_chunks(db_session,vector,keyword_query="Python")
    assert len(results)==1
    assert results[0].document.deleted_at is None
    assert results[0].document.owner_id is None
    private=search_chunks(db_session,vector,keyword_query="Python",owner_id=999)
    assert len(private)==1
    assert private[0].document.owner_id==999
