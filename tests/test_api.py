"""REST API 集成测试。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    """健康检查返回知识库与工具统计。"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["knowledge_documents"] == 12
    assert data["knowledge_chunks"] >= 40
    assert len(data["tools"]) == 10


def test_index_page(client: TestClient) -> None:
    """根路径应返回单页工作台。"""
    response = client.get("/")
    assert response.status_code == 200
    assert "知行" in response.text
    assert "/static/app.js" in response.text


def test_login_page_has_no_initial_accounts_or_hints() -> None:
    """登录页不应展示演示账号，也不应给输入框灰色 placeholder。"""
    path = Path(__file__).resolve().parents[1] / "static" / "index.html"
    html = path.read_text(encoding="utf-8")
    assert "data-demo-account" not in html
    assert "staff-demo" not in html
    assert 'autocomplete="username"' not in html
    assert 'placeholder="名册中的' not in html
    assert 'placeholder="与名册一致' not in html
    assert 'placeholder="例如 admin' not in html
    assert 'placeholder="学生：学号后六位' not in html


def test_session_lifecycle(client: TestClient) -> None:
    """会话创建、列表、详情与删除。"""
    created = client.post("/api/v1/sessions", json={"title": "测试会话"})
    assert created.status_code == 201
    session_id = created.json()["id"]

    listing = client.get("/api/v1/sessions")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["title"] == "测试会话"

    detail = client.get(f"/api/v1/sessions/{session_id}")
    assert detail.status_code == 200
    assert detail.json()["messages"] == []

    deleted = client.delete(f"/api/v1/sessions/{session_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    missing = client.get(f"/api/v1/sessions/{session_id}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "session_not_found"


def test_chat_workflow_and_workorder(client: TestClient) -> None:
    """通过 API 跑通补办并查询工单。"""
    session = client.post("/api/v1/sessions", json={}).json()
    session_id = session["id"]

    first = client.post(
        "/api/v1/chat/send",
        json={"session_id": session_id, "message": "我要补办校园卡"},
    )
    assert first.status_code == 200
    payload = first.json()
    assert payload["intent"] == "workflow"
    assert payload["workorder"]["status"] == "awaiting_input"
    workorder_id = payload["workorder"]["id"]

    second = client.post(
        "/api/v1/chat/send",
        json={"session_id": session_id, "message": "2025001002 独墅湖"},
    )
    assert second.status_code == 200
    assert second.json()["requires_confirmation"] is True

    confirmed = client.post(
        f"/api/v1/chat/sessions/{session_id}/confirm",
        json={"action": "confirm"},
    )
    assert confirmed.status_code == 200
    completed = confirmed.json()["workorder"]
    assert completed["status"] == "completed"
    assert completed["receipt_number"].startswith("CARD")

    listing = client.get("/api/v1/workorders")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    detail = client.get(f"/api/v1/workorders/{workorder_id}")
    assert detail.status_code == 200
    assert detail.json()["receipt_number"] == completed["receipt_number"]

    audit = client.get(f"/api/v1/workorders/{workorder_id}/audit")
    assert audit.status_code == 200
    assert audit.json()["total"] > 0


def test_knowledge_api(client: TestClient) -> None:
    """知识库列表、详情与混合检索接口。"""
    documents = client.get("/api/v1/knowledge/documents")
    assert documents.status_code == 200
    assert documents.json()["total"] == 12
    doc_id = documents.json()["items"][0]["id"]

    detail = client.get(f"/api/v1/knowledge/documents/{doc_id}")
    assert detail.status_code == 200
    assert detail.json()["sections"]

    search = client.get("/api/v1/knowledge/search", params={"q": "校园卡补办要多少钱"})
    assert search.status_code == 200
    results = search.json()["results"]
    assert results
    assert results[0]["doc_id"] == "reg-card"
    assert "coverage" in results[0]


def test_evaluation_api(client: TestClient) -> None:
    """评测接口返回指标。"""
    report = client.post("/api/v1/evaluation/run")
    assert report.status_code == 200
    data = report.json()
    assert data["dataset_size"] >= 20
    assert data["recall_at_5"] >= 0.85

    latest = client.get("/api/v1/evaluation/latest")
    assert latest.status_code == 200
    assert latest.json()["run_id"] == data["run_id"]


def test_confirm_without_active_workorder(client: TestClient) -> None:
    """没有待确认工单时应返回 409。"""
    session = client.post("/api/v1/sessions", json={}).json()
    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/confirm",
        json={"action": "confirm"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "workflow_state_invalid"


def test_validation_error_envelope(client: TestClient) -> None:
    """空消息应返回统一校验错误结构。"""
    response = client.post("/api/v1/chat/send", json={"message": "   "})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
