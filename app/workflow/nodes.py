"""工作流节点实现。

节点统一签名 ``execute(ctx, node, engine) -> NodeResult``。
节点只负责自身语义（抽取、判断、调用、确认、格式化），
节点之间的跳转由声明式边与 :mod:`app.workflow.conditions` 决定。
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from typing import Any

from app.core.enums import AuditEventType, NodeType, WorkOrderStatus
from app.llm.prompt_templates import WORKFLOW_MESSAGES
from app.models.domain import (
    NodeResult,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowNodeDef,
)
from app.models.schema import ToolCallRecord
from app.workflow.conditions import evaluate

ALLOWED_CAMPUS: tuple[str, ...] = ("天赐庄", "独墅湖", "阳澄湖")
CONFIRM_WORDS = {"确认", "确认提交", "提交", "可以", "好的", "同意", "行", "yes", "y"}
CANCEL_WORDS = {"取消", "不办了", "算了", "不要了", "no", "n"}
_STUDENT_ID_RE = re.compile(r"(?<!\d)(\d{10})(?!\d)")
_DIGITS_RE = re.compile(r"(?<!\d)(\d{6,})(?!\d)")


async def execute_node(
    ctx: WorkflowContext,
    node: WorkflowNodeDef,
    engine: Any,
) -> NodeResult:
    """按节点类型分发执行。"""
    handlers = {
        NodeType.START: _node_start,
        NodeType.INTENT: _node_start,
        NodeType.PARAMETER_EXTRACT: _node_parameter_extract,
        NodeType.CONDITION: _node_condition,
        NodeType.TOOL_CALL: _node_tool_call,
        NodeType.CONFIRMATION: _node_confirmation,
        NodeType.APPROVAL: _node_approval,
        NodeType.RESULT: _node_result,
        NodeType.HUMAN_HANDOFF: _node_handoff,
        NodeType.END: _node_end,
    }
    handler = handlers.get(node.node_type)
    if handler is None:
        return NodeResult.fail(f"不支持的节点类型: {node.node_type}")
    return await handler(ctx, node, engine)


# --------------------------------------------------------------------- 基础工具
def _definition(ctx: WorkflowContext) -> WorkflowDefinition:
    if ctx.definition is None:
        raise RuntimeError("工作流定义未注入")
    return ctx.definition


def _default_next(node: WorkflowNodeDef, definition: WorkflowDefinition) -> str | None:
    """返回节点的默认出边目标。"""
    for edge in definition.outgoing_edges(node.id):
        if edge.condition is None:
            return edge.target
    return None


def _conditional_next(ctx: WorkflowContext, node: WorkflowNodeDef) -> str | None:
    """按声明顺序评估条件边，返回第一个命中的目标。"""
    definition = _definition(ctx)
    fallback: str | None = None
    for edge in definition.outgoing_edges(node.id):
        if edge.condition is None:
            fallback = edge.target
            continue
        if evaluate(edge.condition, ctx):
            return edge.target
    return fallback


def _extract_student_id(text: str) -> tuple[str | None, str | None]:
    """抽取 10 位学号，返回 ``(学号, 错误说明)``。"""
    match = _STUDENT_ID_RE.search(text)
    if match:
        return match.group(1), None
    bad = _DIGITS_RE.search(text)
    if bad:
        return None, f"学号“{bad.group(1)}”不是 10 位数字"
    return None, None


def _extract_campus(text: str) -> str | None:
    """从文本中抽取校区。"""
    for campus in ALLOWED_CAMPUS:
        if campus in text:
            return campus
    return None


def _slot_label(slots: dict[str, Any]) -> str:
    """格式化预约时段。"""
    recommended = slots.get("recommended") or {}
    if not recommended:
        return "待定"
    return f"{recommended.get('date', '')} {recommended.get('weekday', '')} {recommended.get('time', '')}".strip()


def _json_summary(data: dict[str, Any], limit: int = 180) -> str:
    """把工具结果压缩成可读摘要。"""
    text = json.dumps(data, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "…"


# --------------------------------------------------------------------- 节点
async def _node_start(
    ctx: WorkflowContext,
    node: WorkflowNodeDef,
    engine: Any,
) -> NodeResult:
    """开始节点：直接进入默认下一节点。"""
    del engine
    next_node = _default_next(node, _definition(ctx))
    if not next_node:
        return NodeResult.fail("开始节点缺少出边")
    return NodeResult.go(next_node)


async def _node_parameter_extract(
    ctx: WorkflowContext,
    node: WorkflowNodeDef,
    engine: Any,
) -> NodeResult:
    """从用户输入中抽取学号与校区，缺失或非法时暂停提问。"""
    del engine
    text = ctx.user_input.strip()
    invalid: list[str] = []

    student_id, error = _extract_student_id(text)
    if student_id:
        ctx.set_variable("student_id", student_id)
    elif error:
        invalid.append(error)

    campus = _extract_campus(text)
    if campus:
        ctx.set_variable("campus", campus)
    elif "校区" in text and any(word in text for word in ("东校区", "西校区", "北校区")):
        invalid.append("校区只能是天赐庄、独墅湖、阳澄湖")

    fields = node.config.get("fields", [])
    if "repair_category" in fields:
        category = "网络"
        if any(word in text for word in ("水电", "空调", "门锁", "照明", "热水")):
            category = "生活设施"
        elif any(word in text for word in ("网络", "WiFi", "wifi", "断网", "网线", "路由器")):
            category = "网络"
        ctx.set_variable("repair_category", category)
    if "description" in fields:
        ctx.set_variable("description", text)
    if "leave_days" in fields:
        match = re.search(r"(\d+)\s*天", text)
        ctx.set_variable("leave_days", int(match.group(1)) if match else 1)
    if "reason" in fields:
        ctx.set_variable("reason", text)

    missing: list[str] = []
    if not ctx.get_variable("student_id"):
        missing.append("学号")
    if not ctx.get_variable("campus"):
        missing.append("校区")

    if invalid:
        ctx.add_trace("node", "参数校验未通过", detail="；".join(invalid), status="warning")
        return NodeResult.pause(
            WORKFLOW_MESSAGES["invalid_params"].format(invalid="；".join(invalid)),
            suggested_actions=["2025001001，独墅湖", "2025001003，阳澄湖"],
            data={"invalid": invalid},
        )

    if missing:
        template = WORKFLOW_MESSAGES["ask_params_again"] if len(missing) == 1 else WORKFLOW_MESSAGES["ask_params"]
        message = template.format(missing="、".join(missing)) if missing else WORKFLOW_MESSAGES["ask_params"]
        return NodeResult.pause(
            message,
            suggested_actions=["2025001001，独墅湖", "2025001003，阳澄湖"],
            data={"missing": missing},
        )

    # 参数齐全，进入默认下一节点
    next_node = _default_next(node, _definition(ctx))
    if not next_node:
        return NodeResult.fail("参数抽取节点缺少出边")
    return NodeResult.go(
        next_node,
        data={
            "student_id": ctx.get_variable("student_id"),
            "campus": ctx.get_variable("campus"),
        },
    )


async def _node_condition(
    ctx: WorkflowContext,
    node: WorkflowNodeDef,
    engine: Any,
) -> NodeResult:
    """条件分支节点。"""
    del engine
    next_node = _conditional_next(ctx, node)
    if not next_node:
        return NodeResult.fail(f"条件节点 {node.id} 没有命中的分支")
    ctx.add_trace("node", f"分支判断 · {node.name}", detail=f"进入 {next_node}")
    return NodeResult.go(next_node)


async def _node_tool_call(
    ctx: WorkflowContext,
    node: WorkflowNodeDef,
    engine: Any,
) -> NodeResult:
    """调用业务工具，失败自动重试，仍失败则转人工。"""
    del engine
    definition = _definition(ctx)
    config = node.config
    tool_name = str(config["tool"])
    save_as = config.get("save_as")
    idempotent = bool(config.get("idempotent"))
    key = ""

    if idempotent:
        key = _idempotency_key(config, ctx)
        ctx.workorder.idempotency_key = key
        ctx.set_variable("idempotency_key", key)
        existing_id = ctx.idempotency.get(key)
        if existing_id:
            original = (
                ctx.workorder_store.get(existing_id) if ctx.workorder_store is not None else None
            )
            if original is not None and original.receipt_number:
                ctx.audit.record(
                    AuditEventType.IDEMPOTENCY.value,
                    ctx.session_id,
                    ctx.workorder.id,
                    {
                        "idempotency_key": key,
                        "existing_workorder": original.id,
                        "receipt": original.receipt_number,
                        "action": "return_existing",
                    },
                )
                ctx.add_trace(
                    "idempotency",
                    "命中幂等键，返回原回执",
                    detail=f"原工单 {original.receipt_number}",
                    data={"key": key, "receipt": original.receipt_number},
                )
                return NodeResult.finish(
                    WORKFLOW_MESSAGES["duplicate"].format(receipt=original.receipt_number),
                    data={
                        "duplicate": True,
                        "original_id": original.id,
                        "receipt": original.receipt_number,
                    },
                )
            ctx.idempotency.delete(key)

    # 幂等键生成后再解析工具参数，确保 $idempotency_key 能取到值
    arguments = _resolve_arguments(config.get("arguments", {}), ctx)
    attempts = 1 + max(0, int(ctx.settings.tool_max_retries))
    last_error = "未知错误"
    for attempt in range(1, attempts + 1):
        result = await ctx.tool_registry.execute(tool_name, arguments)
        record = ToolCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            success=result.success,
            latency_ms=result.latency_ms,
            error=result.error_message,
            result_summary=_json_summary(result.data) if result.success else None,
        )
        ctx.tool_records.append(record)
        ctx.audit.record(
            AuditEventType.TOOL_CALL.value,
            ctx.session_id,
            ctx.workorder.id,
            {
                "tool": tool_name,
                "arguments": arguments,
                "attempt": attempt,
                "success": result.success,
                "latency_ms": result.latency_ms,
                "error": result.error_message,
                "result": result.data if result.success else None,
            },
        )
        ctx.add_trace(
            "tool",
            f"{tool_name}",
            detail=(
                f"第 {attempt} 次调用成功，耗时 {result.latency_ms}ms"
                if result.success
                else f"第 {attempt} 次调用失败：{result.error_message}"
            ),
            status="success" if result.success else "failed",
            latency_ms=result.latency_ms,
            data={"tool": tool_name, "arguments": arguments},
        )
        if result.success:
            if save_as:
                ctx.set_variable(save_as, result.data)
                if isinstance(result.data, dict):
                    for id_key in ("ticket_id", "order_id", "leave_id", "id"):
                        if result.data.get(id_key):
                            ctx.set_variable(f"{save_as}_id", result.data[id_key])
                            break
            if tool_name == "card.query_available_slots":
                recommended = (result.data or {}).get("recommended") or {}
                if recommended.get("slot_id"):
                    ctx.set_variable("slot_id", recommended["slot_id"])
            if tool_name == "card.submit_reissue_order":
                receipt = str(result.data.get("receipt_number", ""))
                ctx.workorder.receipt_number = receipt
                ctx.workorder.status = WorkOrderStatus.IN_PROGRESS
                if key:
                    ctx.idempotency.set(key, ctx.workorder.id)
            next_node = _default_next(node, definition)
            if not next_node:
                return NodeResult.fail(f"工具节点 {node.id} 缺少出边")
            return NodeResult.go(next_node, data=result.data)

        last_error = result.error_message or "未知错误"

    ctx.workorder.error_message = last_error
    ctx.audit.record(
        AuditEventType.HANDOFF.value,
        ctx.session_id,
        ctx.workorder.id,
        {"reason": "tool_failure", "tool": tool_name, "error": last_error},
    )
    ctx.add_trace("handoff", "工具连续失败，转人工", detail=last_error, status="failed")
    return NodeResult.handoff(WORKFLOW_MESSAGES["timeout"], error=last_error)


def _resolve_arguments(template: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
    """解析工具参数：``$name`` 从工作流变量取值。"""
    resolved: dict[str, Any] = {}
    for key, value in template.items():
        if isinstance(value, str) and value.startswith("$"):
            resolved[key] = ctx.get_variable(value[1:])
        else:
            resolved[key] = value
    return resolved


def _idempotency_key(config: dict[str, Any], ctx: WorkflowContext) -> str:
    """按模板生成幂等键。"""
    template = str(config.get("idempotency_key_template", "{workflow_type}:{student_id}:{date}"))
    values = {
        "workflow_type": ctx.workorder.workflow_type,
        "student_id": ctx.get_variable("student_id", ""),
        "campus": ctx.get_variable("campus", ""),
        "date": date.today().isoformat(),
    }
    return template.format(**values)


async def _node_confirmation(
    ctx: WorkflowContext,
    node: WorkflowNodeDef,
    engine: Any,
) -> NodeResult:
    """人工确认节点：展示预约、材料与费用，等待确认/取消。"""
    del engine
    slots = ctx.get_variable("slots") or {}
    fee = float(ctx.settings.card_reissue_fee)
    template = node.config.get("message_template")
    if template:
        values = defaultdict(
            str,
            {
                "student_id": ctx.get_variable("student_id", ""),
                "campus": ctx.get_variable("campus", ""),
                "repair_category": ctx.get_variable("repair_category", ""),
                "description": ctx.get_variable("description", ""),
                "slot": _slot_label(slots),
                "fee": f"{fee:g}",
            },
        )
        summary = str(template).format_map(values)
    else:
        summary = WORKFLOW_MESSAGES["confirm"].format(
            student_id=ctx.get_variable("student_id", ""),
            campus=ctx.get_variable("campus", ""),
            slot=_slot_label(slots),
            fee=f"{fee:g}",
        )

    if ctx.confirmed is None:
        ctx.workorder.status = WorkOrderStatus.AWAITING_CONFIRM
        return NodeResult.pause(
            summary,
            suggested_actions=["确认提交", "取消"],
            requires_confirmation=True,
            data={"summary": summary},
        )

    ctx.audit.record(
        AuditEventType.CONFIRMATION.value,
        ctx.session_id,
        ctx.workorder.id,
        {"action": "confirm" if ctx.confirmed else "cancel", "node": node.id},
    )
    next_node = _conditional_next(ctx, node)
    if not next_node:
        return NodeResult.fail("确认节点没有匹配的分支")
    return NodeResult.go(next_node, data={"confirmed": ctx.confirmed})


async def _node_approval(
    ctx: WorkflowContext,
    node: WorkflowNodeDef,
    engine: Any,
) -> NodeResult:
    """工作人员审批节点：暂停等待审批，审批后按 confirmed/cancelled 分支。"""
    del engine
    role = str(node.config.get("approval_role", "counselor"))
    template = node.config.get("message_template")
    values = defaultdict(
        str,
        {
            "student_id": ctx.get_variable("student_id", ""),
            "campus": ctx.get_variable("campus", ""),
            "leave_days": ctx.get_variable("leave_days", ""),
            "reason": ctx.get_variable("reason", ""),
            "approval_role": role,
        },
    )
    summary = (
        str(template).format_map(values)
        if template
        else f"待 {role} 审批：学号 {values['student_id']}，请假 {values['leave_days']} 天。"
    )
    if ctx.confirmed is None:
        ctx.workorder.status = WorkOrderStatus.AWAITING_APPROVAL
        ctx.workorder.approval_role = role
        return NodeResult.pause(
            summary,
            suggested_actions=["等待工作人员审批"],
            requires_confirmation=False,
            data={"approval_role": role, "summary": summary},
        )
    ctx.audit.record(
        AuditEventType.CONFIRMATION.value,
        ctx.session_id,
        ctx.workorder.id,
        {"action": "approved" if ctx.confirmed else "rejected", "node": node.id},
    )
    next_node = _conditional_next(ctx, node)
    if not next_node:
        return NodeResult.fail("审批节点没有匹配的分支")
    approved = ctx.confirmed
    # 一次审批只消费一次确认，后续审批节点必须重新等待工作人员。
    ctx.confirmed = None
    return NodeResult.go(next_node, data={"approved": approved})


async def _node_result(
    ctx: WorkflowContext,
    node: WorkflowNodeDef,
    engine: Any,
) -> NodeResult:
    """结果节点：格式化最终文案并结束流程。"""
    del engine
    kind = str(node.config.get("result_kind", "success"))
    fee = float(ctx.settings.card_reissue_fee)
    order = ctx.get_variable("order") or {}
    slots = ctx.get_variable("slots") or {}

    generic_template = node.config.get("message_template")
    if generic_template:
        values = defaultdict(
            str,
            {
                "receipt": order.get("receipt_number", ctx.workorder.receipt_number or ""),
                "ticket_id": ctx.get_variable("repair_ticket_id", ""),
                "student_id": ctx.get_variable("student_id", ""),
                "campus": ctx.get_variable("campus", ""),
                "repair_category": ctx.get_variable("repair_category", ""),
                "description": ctx.get_variable("description", ""),
            },
        )
        message = str(generic_template).format_map(values)
        if kind == "success":
            ctx.workorder.result = order
            receipt = order.get("receipt_number") or ctx.get_variable("repair_ticket_id", "")
            ctx.workorder.receipt_number = str(receipt or ctx.workorder.receipt_number or "")
            ctx.workorder.status = WorkOrderStatus.COMPLETED
            ctx.add_trace("node", "工单已完成", detail=ctx.workorder.receipt_number)
            return NodeResult.finish(
                message,
                data={**order, "status": "completed"},
                suggested_actions=["查看工单", "再报一单"],
            )
        if kind == "cancelled":
            ctx.workorder.status = WorkOrderStatus.CANCELLED
            ctx.workorder.result = {"reason": "cancelled"}
            ctx.add_trace("node", "用户取消")
            return NodeResult.finish(
                message,
                data={"reason": "cancelled", "status": "cancelled"},
                suggested_actions=["重新报修"],
            )

    if kind == "success":
        message = WORKFLOW_MESSAGES["success"].format(
            receipt=order.get("receipt_number", ctx.workorder.receipt_number),
            slot=_slot_label(slots),
            location=order.get("location", slots.get("location", "卡务中心")),
            fee=f"{fee:g}",
        )
        ctx.workorder.result = order
        ctx.workorder.receipt_number = str(
            order.get("receipt_number", ctx.workorder.receipt_number)
        )
        ctx.workorder.status = WorkOrderStatus.COMPLETED
        ctx.add_trace("node", "工单已完成", detail=ctx.workorder.receipt_number)
        return NodeResult.finish(message, data=order, suggested_actions=["查看工单", "再办一张"])

    if kind == "invalid_student":
        profile = ctx.get_variable("student_profile") or {}
        message = WORKFLOW_MESSAGES["invalid_student"].format(
            student_id=profile.get("student_id", ctx.get_variable("student_id", ""))
        )
        ctx.workorder.status = WorkOrderStatus.FAILED
        ctx.workorder.error_message = "学号不存在"
        ctx.workorder.result = {"reason": "invalid_student"}
        ctx.add_trace("node", "学号校验失败", status="failed")
        return NodeResult.finish(message, data={"reason": "invalid_student", "status": "failed"})

    if kind == "arrears":
        balance = ctx.get_variable("balance") or {}
        amount = float(balance.get("arrears", 0.0))
        message = WORKFLOW_MESSAGES["arrears"].format(amount=f"{amount:.2f}")
        ctx.workorder.status = WorkOrderStatus.FAILED
        ctx.workorder.error_message = f"欠费 {amount:.2f} 元"
        ctx.workorder.result = {"reason": "arrears", "arrears": amount}
        ctx.add_trace("node", "存在欠费，流程中止", detail=f"{amount:.2f} 元", status="warning")
        return NodeResult.finish(
            message,
            data={"reason": "arrears", "arrears": amount, "status": "failed"},
            suggested_actions=["如何缴清欠费"],
        )

    if kind == "cancelled":
        ctx.workorder.status = WorkOrderStatus.CANCELLED
        ctx.workorder.result = {"reason": "cancelled"}
        ctx.add_trace("node", "用户取消办理", status="warning")
        return NodeResult.finish(
            WORKFLOW_MESSAGES["cancelled"],
            data={"reason": "cancelled", "status": "cancelled"},
        )

    ctx.workorder.status = WorkOrderStatus.FAILED
    return NodeResult.finish("流程已结束。", data={"reason": kind, "status": "failed"})


async def _node_handoff(
    ctx: WorkflowContext,
    node: WorkflowNodeDef,
    engine: Any,
) -> NodeResult:
    """显式转人工节点。"""
    del node, engine
    ctx.workorder.status = WorkOrderStatus.TRANSFERRED_HUMAN
    return NodeResult.handoff(WORKFLOW_MESSAGES["timeout"])


async def _node_end(
    ctx: WorkflowContext,
    node: WorkflowNodeDef,
    engine: Any,
) -> NodeResult:
    """结束节点。"""
    del node, engine
    return NodeResult.finish("流程已结束。", data={"status": ctx.workorder.status.value})
