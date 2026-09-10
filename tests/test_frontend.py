"""前端静态页面托管测试。"""

from fastapi.testclient import TestClient


def test_index_page_served_at_root(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "知识库问答" in resp.text


def test_static_assets_served(client: TestClient) -> None:
    for path in ("/style.css", "/app.js"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert len(resp.content) > 0


def test_api_routes_take_priority_over_static(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/v1/info").status_code == 200
    assert client.get("/api/v1/documents").status_code == 200
