"""校园网络报修工具（演示 Mock）。"""

from __future__ import annotations

from typing import Any

from app.models.domain import ToolResult
from app.tools.base import BaseTool
from app.tools.registry import register_tool


@register_tool
class RepairCreateTicketTool(BaseTool):
    """生成待确认的网络报修单。"""

    name = "repair.create_ticket"
    description = "根据学号、校区、故障类型和描述生成网络报修草稿。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "pattern": "^\\d{10}$"},
            "campus": {"type": "string"},
            "category": {"type": "string"},
            "description": {"type": "string"},
        },
        "required": ["student_id", "campus", "description"],
    }
    category = "网络报修"

    async def execute(self, **kwargs: Any) -> ToolResult:
        self._require(kwargs, "student_id", "campus", "description")
        data = await self._service.create_repair_ticket(
            student_id=str(kwargs["student_id"]),
            campus=str(kwargs["campus"]),
            category=str(kwargs.get("category") or "网络"),
            description=str(kwargs["description"]),
        )
        return ToolResult.ok(data)


@register_tool
class RepairSubmitTicketTool(BaseTool):
    """提交网络报修单并返回回执。"""

    name = "repair.submit_ticket"
    description = "提交报修单；同一幂等键返回原回执。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string"},
            "idempotency_key": {"type": "string"},
        },
        "required": ["ticket_id", "idempotency_key"],
    }
    category = "网络报修"

    async def execute(self, **kwargs: Any) -> ToolResult:
        self._require(kwargs, "ticket_id", "idempotency_key")
        data = await self._service.submit_repair_ticket(
            ticket_id=str(kwargs["ticket_id"]),
            idempotency_key=str(kwargs["idempotency_key"]),
        )
        return ToolResult.ok(data)
