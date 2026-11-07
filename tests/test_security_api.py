"""HTTP 层权限回归：越权、学生库、坐席、审批、Token 篡改。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import reset_settings_cache
from app.deps import reset_container
from app.main import create_app
from app.student_registry import StudentRegistry


@pytest.fixture()
def secured_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "data"
    registry_dir = tmp_path / "registry"
    learning_dir = tmp_path / "learning"
    monkeypatch.setenv("CAMPUS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("CAMPUS_STUDENT_REGISTRY_DIR", str(registry_dir))
    monkeypatch.setenv("CAMPUS_LEARNING_DIR", str(learning_dir))
    monkeypatch.setenv("CAMPUS_AUTH_ENABLED", "true")
    monkeypatch.setenv("CAMPUS_AUTH_SECRET", "security-test-secret")
    monkeypatch.setenv("CAMPUS_LLM_SIMULATE_DELAY", "false")
    monkeypatch.setenv("CAMPUS_TOOL_SIMULATE_DELAY", "false")
    reset_settings_cache()
    reset_container()
    registry = StudentRegistry(registry_dir / "students.db")
    registry.upsert_batch(
        [
            {
                "student_id": "2527405998",
                "name": "测试甲",
                "major": "计算机科学与技术",
                "class_name": "计25测试班",
                "phone": "13800138000",
                "gender": "男",
                "dorm_building": "本9",
                "dorm_room": "101",
                "campus": None,
                "status": "active",
                "notes": None,
                "source_row": 2,
            },
            {
                "student_id": "2527405999",
                "name": "测试乙",
                "major": "计算机科学与技术",
                "class_name": "计25测试班",
                "phone": "13800138001",
                "gender": "女",
                "dorm_building": "本9",
                "dorm_room": "102",
                "campus": None,
                "status": "active",
                "notes": None,
                "source_row": 3,
            },
        ],
        source_file="security-test.xlsx",
        source_sha256="security-test",
        college="计算机科学与技术学院",
        cohort="2025",
    )
    app = create_app()
    with TestClient(app) as client:
        yield client
    reset_container()
    reset_settings_cache()


def _login(client: TestClient, student_id: str, name: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"student_id": student_id, "name": name, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_http_permission_boundaries(secured_client: TestClient) -> None:
    client = secured_client
    assert client.get("/api/v1/sessions").status_code == 401

    user_a = _login(client, "2527405998", "测试甲", "405998")
    user_b = _login(client, "2527405999", "测试乙", "405999")

    session = client.post("/api/v1/sessions", json={}, headers=user_a).json()
    assert client.get(f"/api/v1/sessions/{session['id']}", headers=user_b).status_code == 403
    assert client.get(f"/api/v1/sessions/{session['id']}", headers=user_a).status_code == 200

    assert client.get("/api/v1/students", headers=user_a).status_code == 403
    assert client.get("/api/v1/students/2527405998", headers=user_a).status_code == 200
    assert client.get("/api/v1/students/2527405999", headers=user_a).status_code == 403
    own = client.get("/api/v1/students/2527405998", headers=user_a).json()
    assert own["phone_masked"] == "138****8000"

    assert client.get("/api/v1/handoff/queue", headers=user_a).status_code == 403
    assert client.get("/api/v1/approvals/queue", headers=user_a).status_code == 403

    counselor = client.post(
        "/api/v1/auth/login",
        json={"username": "counselor", "password": "counselor123"},
    )
    assert counselor.status_code == 200
    counselor_headers = {"Authorization": f"Bearer {counselor.json()['token']}"}
    assert client.get("/api/v1/handoff/queue", headers=counselor_headers).status_code == 200
    assert client.get("/api/v1/approvals/queue", headers=counselor_headers).status_code == 200
    assert client.get("/api/v1/audit/verify", headers=counselor_headers).status_code == 403

    admin = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    admin_headers = {"Authorization": f"Bearer {admin.json()['token']}"}
    verify = client.get("/api/v1/audit/verify", headers=admin_headers)
    assert verify.status_code == 200
    assert verify.json()["valid"] is True

    bad_token = {"Authorization": user_a["Authorization"] + "x"}
    assert client.get("/api/v1/sessions", headers=bad_token).status_code == 401
