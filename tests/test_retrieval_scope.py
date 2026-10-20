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

def test_idf_reranking_recovers_rare_term_from_long_evidence(db_session, fake_embedder):
    query="common rare"
    for name,text in [("rare.txt","common rare "+" ".join("extra"+str(i) for i in range(50))),
                      ("common.txt","common")]:
        doc=Document(filename=name,extension=".txt")
        db_session.add(doc)
        db_session.flush()
        db_session.add(Chunk(document_id=doc.id,chunk_index=0,content=text,
                             embedding=vec_to_bytes(fake_embedder.embed([text])[0])))
    db_session.commit()
    kwargs=dict(top_k=1,keyword_query=query,vector_weight=0,keyword_weight=1)
    vector=fake_embedder.embed([query])[0]
    assert search_chunks(db_session,vector,keyword_idf=False,**kwargs)[0].document.filename=="common.txt"
    assert search_chunks(db_session,vector,keyword_idf=True,**kwargs)[0].document.filename=="rare.txt"
