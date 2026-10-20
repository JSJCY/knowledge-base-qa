from tests.test_chat import _upload_kb


def test_api_rejects_nonempty_unstructured_hallucination(client, fake_llm, monkeypatch):
    _upload_kb(client)
    monkeypatch.setattr(fake_llm,"chat",lambda messages:"FastAPI is a Java database.")
    body=client.post("/api/v1/chat",json={"question":"FastAPI 是什么框架？"}).json()
    assert body["quality"]["status"]=="rejected"
    assert body["citations"]==[]
    assert "Java" not in body["answer"]
    history=client.get(f"/api/v1/conversations/{body['conversation_id']}").json()
    assert history["messages"][-1]["quality"]["status"]=="rejected"


def test_stream_never_exposes_invalid_model_tokens(client, fake_llm, monkeypatch):
    _upload_kb(client)
    monkeypatch.setattr(fake_llm,"chat",lambda messages:"EXPOSE_UNSUPPORTED_FACT")
    response=client.post("/api/v1/chat/stream",json={"question":"FastAPI 是什么框架？"})
    assert "event: delta" in response.text
    # Raw output is retained in quality metadata, but never sent as an answer delta.
    delta=response.text.split("event: done")[0]
    assert "EXPOSE_UNSUPPORTED_FACT" not in delta
    assert "未找到足够相关" in delta
