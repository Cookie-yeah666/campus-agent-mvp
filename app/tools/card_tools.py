"""校园卡与学籍相关工具。

工具名采用 ``服务.动作`` 命名，模拟 MCP 插件通过统一协议
调用校园业务系统的形态。
"""

from __future__ import annotations

from typing import Any

from app.models.domain import ToolResult
from app.tools.base import BaseTool
from app.tools.registry import register_tool

_STUDENT_SCHEMA = {
    "type": "object",
    "properties": {
        "student_id": {"type": "string", "description": "10 位数字学号", "pattern": "^\\d{10}$"}
    },
    "required": ["student_id"],
}


@register_tool
class StudentQueryProfileTool(BaseTool):
    """根据学号查询学籍信息。"""

    name = "student.query_profile"
    description = "根据学号查询学生姓名、学院、校区与在籍状态，用于校验学号有效性。"
    parameters_schema = _STUDENT_SCHEMA
    category = "学籍服务"

    async def execute(self, **kwargs: Any) -> ToolResult:
        """查询学籍。"""
        self._require(kwargs, "student_id")
        data = await self._service.query_profile(str(kwargs["student_id"]))
        return ToolResult.ok(data)


@register_tool
class CardQueryLossTool(BaseTool):
    """查询校园卡挂失状态。"""

    name = "card.query_loss_status"
    description = "查询指定学号校园卡是否已挂失，以及挂失时间。"
    parameters_schema = _STUDENT_SCHEMA
    category = "校园卡"

    async def execute(self, **kwargs: Any) -> ToolResult:
        """查询挂失状态。"""
        self._require(kwargs, "student_id")
        data = await self._service.query_loss_status(str(kwargs["student_id"]))
        return ToolResult.ok(data)


@register_tool
class CardReportLossTool(BaseTool):
    """提交校园卡挂失。"""

    name = "card.report_loss"
    description = "为指定学号办理校园卡挂失，重复调用保持幂等。"
    parameters_schema = _STUDENT_SCHEMA
    category = "校园卡"

    async def execute(self, **kwargs: Any) -> ToolResult:
        """提交挂失。"""
        self._require(kwargs, "student_id")
        data = await self._service.report_loss(str(kwargs["student_id"]))
        return ToolResult.ok(data)


@register_tool
class CardQueryBalanceTool(BaseTool):
    """查询校园卡余额与欠费。"""

    name = "card.query_balance"
    description = "查询校园卡电子钱包余额；余额为负时返回欠费金额。"
    parameters_schema = _STUDENT_SCHEMA
    category = "校园卡"

    async def execute(self, **kwargs: Any) -> ToolResult:
        """查询余额。"""
        self._require(kwargs, "student_id")
        data = await self._service.query_balance(str(kwargs["student_id"]))
        return ToolResult.ok(data)


@register_tool
class CardQuerySlotsTool(BaseTool):
    """查询可预约的制卡时段。"""

    name = "card.query_available_slots"
    description = "查询指定校区未来 3 天的校园卡制卡预约时段与取卡地点。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "campus": {
                "type": "string",
                "description": "校区",
                "enum": ["天赐庄", "独墅湖", "阳澄湖"],
            }
        },
        "required": ["campus"],
    }
    category = "校园卡"

    async def execute(self, **kwargs: Any) -> ToolResult:
        """查询时段。"""
        self._require(kwargs, "campus")
        data = await self._service.query_available_slots(str(kwargs["campus"]))
        return ToolResult.ok(data)


@register_tool
class CardSubmitReissueTool(BaseTool):
    """提交校园卡制卡工单。"""

    name = "card.submit_reissue_order"
    description = "提交校园卡补办制卡工单并生成回执编号，按幂等键去重。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "description": "10 位数字学号"},
            "campus": {"type": "string", "description": "校区"},
            "slot_id": {"type": "string", "description": "预约时段 ID"},
            "idempotency_key": {"type": "string", "description": "幂等键"},
            "fee": {"type": "number", "description": "工本费", "default": 20.0},
        },
        "required": ["student_id", "campus", "slot_id", "idempotency_key"],
    }
    category = "校园卡"

    async def execute(self, **kwargs: Any) -> ToolResult:
        """提交工单。"""
        self._require(kwargs, "student_id", "campus", "slot_id", "idempotency_key")
        data = await self._service.submit_reissue_order(
            student_id=str(kwargs["student_id"]),
            campus=str(kwargs["campus"]),
            slot_id=str(kwargs["slot_id"]),
            idempotency_key=str(kwargs["idempotency_key"]),
            fee=float(kwargs.get("fee", 20.0)),
        )
        return ToolResult.ok(data)
