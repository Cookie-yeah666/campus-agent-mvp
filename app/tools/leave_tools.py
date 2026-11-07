"""请假流程工具（演示 Mock）。"""

from __future__ import annotations

from typing import Any

from app.models.domain import ToolResult
from app.tools.base import BaseTool
from app.tools.registry import register_tool


@register_tool
class LeaveCreateRequestTool(BaseTool):
    """生成请假申请草稿。"""

    name = "leave.create_request"
    description = "根据学号、校区、天数和原因生成请假申请草稿。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "pattern": "^\\d{10}$"},
            "campus": {"type": "string"},
            "days": {"type": "integer"},
            "reason": {"type": "string"},
        },
        "required": ["student_id", "campus", "days", "reason"],
    }
    category = "请假"

    async def execute(self, **kwargs: Any) -> ToolResult:
        self._require(kwargs, "student_id", "campus", "days", "reason")
        data = await self._service.create_leave_request(
            student_id=str(kwargs["student_id"]),
            campus=str(kwargs["campus"]),
            days=int(kwargs["days"]),
            reason=str(kwargs["reason"]),
        )
        return ToolResult.ok(data)


@register_tool
class LeaveSubmitRequestTool(BaseTool):
    """提交请假申请并返回回执。"""

    name = "leave.submit_request"
    description = "提交已审批的请假申请；幂等键重复时返回原回执。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "leave_id": {"type": "string"},
            "idempotency_key": {"type": "string"},
        },
        "required": ["leave_id", "idempotency_key"],
    }
    category = "请假"

    async def execute(self, **kwargs: Any) -> ToolResult:
        self._require(kwargs, "leave_id", "idempotency_key")
        data = await self._service.submit_leave_request(
            leave_id=str(kwargs["leave_id"]),
            idempotency_key=str(kwargs["idempotency_key"]),
        )
        return ToolResult.ok(data)
