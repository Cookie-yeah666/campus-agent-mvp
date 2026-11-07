"""真实服务的 API 冒烟检查（不会留下测试会话）。"""

from __future__ import annotations

import os

import httpx

ROOT = os.environ.get("CAMPUS_APP_URL", "http://127.0.0.1:8000").rstrip("/")
BASE = f"{ROOT}/api/v1"


def main() -> None:
    """依次验证健康、首页、会话、问答、工单、评测与文档。"""
    with httpx.Client(timeout=30) as client:
        login = client.post(
            f"{BASE}/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['token']}"

        health = client.get(f"{BASE}/health").json()
        assert health["status"] == "ok"
        assert health["knowledge_documents"] == 12
        print("health:", health["version"], health["knowledge_documents"], "docs")

        index = client.get(f"{ROOT}/")
        docs = client.get(f"{ROOT}/docs")
        assert index.status_code == 200 and "知行" in index.text
        assert docs.status_code == 200
        print("web:", index.status_code, "docs:", docs.status_code)

        session = client.post(f"{BASE}/sessions", json={}).json()
        answer = client.post(
            f"{BASE}/chat/send",
            json={"session_id": session["id"], "message": "校园卡补办要多少钱"},
        ).json()
        assert answer["intent"] == "qa"
        assert "20 元" in answer["message"]["content"]
        assert answer["message"]["citations"]
        print("qa:", answer["message"]["citations"][0]["doc_title"])

        workorders = client.get(f"{BASE}/workorders").json()
        latest = client.get(f"{BASE}/evaluation/latest")
        evaluation = (
            latest.json()
            if latest.status_code == 200
            else client.post(f"{BASE}/evaluation/run").json()
        )
        knowledge = client.get(f"{BASE}/knowledge/documents").json()
        print("workorders:", workorders["total"], "evaluation:", evaluation["recall_at_5"])
        print("knowledge:", knowledge["total"])

        client.delete(f"{BASE}/sessions/{session['id']}")
        print("smoke OK")


if __name__ == "__main__":
    main()
