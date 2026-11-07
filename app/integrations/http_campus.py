"""HTTP 校园业务适配器。

真实校园接口的字段与路径各校不同，本适配器把差异集中在
``_get/_post`` 与几个 response 映射方法里；接新系统时只改本文件或
在网关注入兼容层，Agent/工作流不需要改。

约定契约（可被网关覆盖）：
- GET  /students/{id}
- GET  /students/{id}/card
- POST /students/{id}/card/loss
- GET  /card/slots?campus=...
- POST /card/reissue
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import ToolTimeoutError


class HttpCampusService:
    """通过 HTTP 调用真实/沙箱校园系统。"""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._base_url = settings.integration_base_url.rstrip("/")
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if settings.integration_api_key:
            self._headers["Authorization"] = f"Bearer {settings.integration_api_key}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=settings.integration_timeout_seconds,
            transport=transport,
        )

    async def aclose(self) -> None:
        """关闭连接池。"""
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = await self._client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise ToolTimeoutError(f"校园系统连接失败：{exc}") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"exists": False}
            raise ToolTimeoutError(
                f"校园系统返回 {exc.response.status_code}"
            ) from exc

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(path, json=payload)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise ToolTimeoutError(f"校园系统连接失败：{exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise ToolTimeoutError(
                f"校园系统返回 {exc.response.status_code}"
            ) from exc

    # ------------------------------------------------------------------ 工具契约
    async def query_profile(self, student_id: str) -> dict[str, Any]:
        """查询学籍。"""
        data = await self._get(f"/students/{student_id}")
        if not data.get("exists", True):
            return {"valid": False, "student_id": student_id, "exists": False}
        return {
            "valid": True,
            "exists": True,
            "student_id": data.get("student_id", student_id),
            "name": data.get("name", ""),
            "college": data.get("college", ""),
            "campus": data.get("campus"),
            "grade": data.get("grade", ""),
            "enrolled": data.get("enrolled", True),
            "major": data.get("major"),
            "class_name": data.get("class_name"),
            "cohort": data.get("cohort"),
            "source": "http",
            "simulated_card_state": False,
        }

    async def _card(self, student_id: str) -> dict[str, Any]:
        data = await self._get(f"/students/{student_id}/card")
        return data

    async def query_loss_status(self, student_id: str) -> dict[str, Any]:
        """查询挂失状态。"""
        data = await self._card(student_id)
        if not data.get("exists", True):
            return {"student_id": student_id, "exists": False, "lost": False}
        return {
            "student_id": student_id,
            "exists": True,
            "lost": bool(data.get("lost", False)),
            "reported_at": data.get("reported_at"),
            "source": "http",
            "simulated": False,
        }

    async def report_loss(self, student_id: str) -> dict[str, Any]:
        """提交挂失。"""
        data = await self._post(f"/students/{student_id}/card/loss", {})
        return {
            "student_id": student_id,
            "lost": True,
            "reported_at": data.get("reported_at", datetime.now().isoformat(timespec="seconds")),
            "already_lost": bool(data.get("already_lost", False)),
            "source": "http",
            "simulated": False,
        }

    async def query_balance(self, student_id: str) -> dict[str, Any]:
        """查询余额与欠费。"""
        data = await self._card(student_id)
        if not data.get("exists", True):
            return {"student_id": student_id, "exists": False, "balance": 0.0, "arrears": 0.0}
        balance = round(float(data.get("balance", 0.0)), 2)
        arrears = round(float(data.get("arrears", max(0.0, -balance))), 2)
        return {
            "student_id": student_id,
            "exists": True,
            "balance": balance,
            "arrears": arrears,
            "has_arrears": arrears > 0,
            "source": "http",
            "simulated": False,
        }

    async def query_available_slots(self, campus: str) -> dict[str, Any]:
        """查询预约时段。"""
        data = await self._get("/card/slots", params={"campus": campus})
        slots = data.get("slots", [])
        recommended = data.get("recommended") or (slots[0] if slots else {})
        return {
            "campus": campus,
            "location": data.get("location", ""),
            "slots": slots,
            "recommended": recommended,
            "source": "http",
        }

    async def submit_reissue_order(
        self,
        student_id: str,
        campus: str,
        slot_id: str,
        idempotency_key: str,
        fee: float = 20.0,
    ) -> dict[str, Any]:
        """提交制卡工单。"""
        data = await self._post(
            "/card/reissue",
            {
                "student_id": student_id,
                "campus": campus,
                "slot_id": slot_id,
                "idempotency_key": idempotency_key,
                "fee": fee,
            },
        )
        data.setdefault("student_id", student_id)
        data.setdefault("campus", campus)
        data.setdefault("slot_id", slot_id)
        data.setdefault("fee", fee)
        data.setdefault("source", "http")
        return data

    def list_students(self) -> list[dict[str, Any]]:
        """HTTP 模式下不把全量学生放进系统页，返回空列表。"""
        return []
