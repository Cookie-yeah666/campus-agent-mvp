"""HTTP 校园适配器的契约测试（不访问真实网络）。"""

from __future__ import annotations

import asyncio
import json

import httpx

from app.config import Settings
from app.integrations.http_campus import HttpCampusService


def test_http_adapter_maps_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/students/2527405001":
            return httpx.Response(
                200,
                json={
                    "exists": True,
                    "student_id": "2527405001",
                    "name": "测试学生",
                    "college": "计算机科学与技术学院",
                    "major": "计算机科学与技术",
                    "class_name": "计25测试班",
                    "campus": "天赐庄",
                    "grade": "2025级",
                    "enrolled": True,
                },
            )
        if path == "/students/2527405001/card":
            return httpx.Response(
                200,
                json={"exists": True, "lost": False, "balance": 12.5, "arrears": 0},
            )
        if path == "/card/slots":
            return httpx.Response(
                200,
                json={
                    "campus": "天赐庄",
                    "location": "卡务中心",
                    "slots": [{"slot_id": "2026-11-06-AM", "date": "2026-11-06"}],
                    "recommended": {"slot_id": "2026-11-06-AM"},
                },
            )
        if path == "/card/reissue":
            return httpx.Response(
                200,
                json={"receipt_number": "CARD20261106001", "status": "submitted"},
            )
        return httpx.Response(404, json={"error": "not found"})

    settings = Settings(
        integration_mode="http",
        integration_base_url="http://sandbox.local",
        integration_api_key="test-key",
        integration_timeout_seconds=1,
    )
    service = HttpCampusService(
        settings,
        transport=httpx.MockTransport(handler),
    )

    async def run() -> None:
        profile = await service.query_profile("2527405001")
        assert profile["name"] == "测试学生"
        assert profile["class_name"] == "计25测试班"

        loss = await service.query_loss_status("2527405001")
        assert loss["lost"] is False

        balance = await service.query_balance("2527405001")
        assert balance["balance"] == 12.5

        slots = await service.query_available_slots("天赐庄")
        assert slots["recommended"]["slot_id"] == "2026-11-06-AM"

        order = await service.submit_reissue_order(
            "2527405001",
            "天赐庄",
            "2026-11-06-AM",
            "card_reissue:2527405001:2026-11-06",
        )
        assert order["receipt_number"] == "CARD20261106001"

        await service.aclose()

    asyncio.run(run())
