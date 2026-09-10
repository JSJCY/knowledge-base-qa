KB_TEXT = "FastAPI 是一个现代 Python web 框架，用于构建高性能 API 接口，支持自动生成文档。"


def _upload_kb(client, filename: str = "kb.txt") -> int:
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, KB_TEXT.encode("utf-8"), "text/plain")},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_chat_returns_answer_with_citations(client):
    _upload_kb(client)
    resp = client.post("/api/v1/chat", json={"question": "FastAPI 是什么框架？"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"]
    assert body["llm_mode"] == "fake"
    assert body["conversation_id"] >= 1
    assert len(body["citations"]) >= 1
    top = body["citations"][0]
    assert top["document_filename"] == "kb.txt"
    assert "FastAPI" in top["content"]
    assert top["score"] > 0


def test_chat_system_prompt_contains_retrieved_context(client, fake_llm):
    _upload_kb(client)
    client.post("/api/v1/chat", json={"question": "FastAPI 能做什么？"})
    system = fake_llm.last_messages[0]
    assert system["role"] == "system"
    assert "FastAPI" in system["content"]
    assert "kb.txt" in system["content"]


def test_chat_on_empty_kb(client):
    resp = client.post("/api/v1/chat", json={"question": "任何问题"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["citations"] == []
    assert body["answer"]


def test_chat_conversation_continuity(client, fake_llm):
    _upload_kb(client)
    first = client.post("/api/v1/chat", json={"question": "第一个问题"}).json()
    conv_id = first["conversation_id"]

    second = client.post(
        "/api/v1/chat",
        json={"question": "第二个问题", "conversation_id": conv_id},
    ).json()
    assert second["conversation_id"] == conv_id

    # 第二轮 LLM 输入 = system + 第一轮 user + 第一轮 assistant + 本轮 user
    roles = [m["role"] for m in fake_llm.last_messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert fake_llm.last_messages[1]["content"] == "第一个问题"
    assert fake_llm.last_messages[3]["content"] == "第二个问题"

    detail = client.get(f"/api/v1/conversations/{conv_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["message_count"] == 4
    assert body["title"] == "第一个问题"
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user", "assistant"]
    # assistant 消息带引用
    assert body["messages"][1]["citations"][0]["document_filename"] == "kb.txt"


def test_chat_unknown_conversation_404(client):
    resp = client.post("/api/v1/chat", json={"question": "hi", "conversation_id": 99999})
    assert resp.status_code == 404


def test_chat_empty_question_422(client):
    resp = client.post("/api/v1/chat", json={"question": ""})
    assert resp.status_code == 422


def test_conversation_list_and_delete(client):
    client.post("/api/v1/chat", json={"question": "会话一"})
    client.post("/api/v1/chat", json={"question": "会话二"})

    convs = client.get("/api/v1/conversations")
    assert convs.status_code == 200
    assert len(convs.json()) == 2

    target = convs.json()[0]["id"]
    assert client.delete(f"/api/v1/conversations/{target}").status_code == 204
    assert len(client.get("/api/v1/conversations").json()) == 1
    assert client.get(f"/api/v1/conversations/{target}").status_code == 404
    assert client.delete(f"/api/v1/conversations/{target}").status_code == 404
