"""为本地演示准备会话、工单与评测数据（需服务已启动）。"""

from __future__ import annotations

import json
import os

import httpx

BASE = os.environ.get("CAMPUS_BASE_URL", "http://127.0.0.1:8011/api/v1")


def send(client: httpx.Client, session_id: str, text: str) -> dict:
    """发送一条消息并返回响应。"""
    response = client.post(
        f"{BASE}/chat/send",
        json={"session_id": session_id, "message": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def new_session(client: httpx.Client) -> str:
    """新建会话。"""
    response = client.post(f"{BASE}/sessions", json={}, timeout=20)
    response.raise_for_status()
    return response.json()["id"]


def main() -> None:
    """按顺序准备演示数据。"""
    with httpx.Client() as client:
        login = client.post(
            f"{BASE}/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=20,
        )
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['token']}"

        # 1) 问答 + 多轮追问
        qa = new_session(client)
        send(client, qa, "奖学金申请需要什么材料？")
        send(client, qa, "转专业学生呢")
        print("QA session:", qa)

        # 2) 欠费失败
        arrears = new_session(client)
        send(client, arrears, "我要补办校园卡")
        send(client, arrears, "2025001003 阳澄湖")
        print("Arrears session:", arrears)

        # 3) 工具超时转人工
        timeout = new_session(client)
        send(client, timeout, "我要补办校园卡")
        send(client, timeout, "2025000999 天赐庄")
        print("Timeout session:", timeout)

        # 4) 已完成并生成回执
        completed = new_session(client)
        send(client, completed, "我要补办校园卡")
        send(client, completed, "2025001002 独墅湖")
        response = client.post(
            f"{BASE}/chat/sessions/{completed}/confirm",
            json={"action": "confirm"},
            timeout=60,
        )
        response.raise_for_status()
        receipt = response.json().get("workorder", {}).get("receipt_number")
        print("Completed session:", completed, "receipt:", receipt)

        # 5) 待确认（最后创建，确保位于会话列表顶部）
        pending = new_session(client)
        send(client, pending, "我要补办校园卡")
        send(client, pending, "2025001001 天赐庄")
        print("Pending session:", pending)

        # 6) 评测
        report = client.post(f"{BASE}/evaluation/run", timeout=120)
        report.raise_for_status()
        data = report.json()
        print(json.dumps(
            {
                "recall_at_5": data["recall_at_5"],
                "mrr_at_5": data["mrr_at_5"],
                "avg_latency_ms": data["avg_latency_ms"],
            },
            ensure_ascii=False,
        ))


if __name__ == "__main__":
    main()
