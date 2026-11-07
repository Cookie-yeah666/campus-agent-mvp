"""工作人员审批队列（请假等）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.access import can_view_session
from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.core.enums import AuditEventType, WorkOrderStatus
from app.deps import get_container

router = APIRouter(prefix="/approvals", tags=["审批"])


def _staff(user: AuthUser) -> None:
    if user.role not in {"counselor", "auditor", "admin"}:
        raise HTTPException(403, detail={"code": "staff_only", "message": "仅工作人员可用"})


def _visible(order: Any, user: AuthUser) -> bool:
    if user.role in {"auditor", "admin"}:
        return True
    try:
        session = get_container().session_manager.get(order.session_id or "")
    except Exception:  # noqa: BLE001
        return False
    return can_view_session(user, session)


@router.get("/queue", summary="待审批队列")
def queue(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    _staff(user)
    container = get_container()
    orders = [
        order
        for order in container.workorder_store.list(WorkOrderStatus.AWAITING_APPROVAL)
        if _visible(order, user)
    ]
    items = []
    for order in orders:
        items.append(
            {
                "id": order.id,
                "workflow_type": order.workflow_type,
                "status": order.status.value,
                "approval_role": order.approval_role or "counselor",
                "student_id": order.user_inputs.get("student_id"),
                "campus": order.user_inputs.get("campus"),
                "summary": order.result.get("summary") if order.result else "",
                "session_id": order.session_id,
                "updated_at": order.updated_at.isoformat(),
            }
        )
    return {"items": items, "count": len(items)}


class ApprovalAction(BaseModel):
    note: str = Field(default="", max_length=1000)


@router.post("/{workorder_id}/return", summary="返校销假")
async def return_from_leave(
    workorder_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    container = get_container()
    order = container.workorder_store.get(workorder_id)
    if order.workflow_type != "leave_request":
        raise HTTPException(409, detail={"code": "not_leave", "message": "不是请假工单"})
    if order.status != WorkOrderStatus.COMPLETED:
        raise HTTPException(409, detail={"code": "not_completed", "message": "请假尚未通过"})
    try:
        session = container.session_manager.get(order.session_id or "")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(404, detail={"code": "session_not_found", "message": "会话不存在"}) from exc
    if user.role not in {"admin", "auditor"} and session.owner_id != (user.student_id or user.username):
        raise HTTPException(403, detail={"code": "forbidden", "message": "只能为自己的请假销假"})
    leave_id = order.user_inputs.get("leave_request_id") or order.user_inputs.get("order_id")
    if not leave_id:
        raise HTTPException(400, detail={"code": "leave_id_missing", "message": "缺少请假单号"})
    if not hasattr(container.campus_service, "return_leave"):
        raise HTTPException(
            501,
            detail={"code": "return_not_supported", "message": "当前接入的真实系统尚未提供销假接口"},
        )
    try:
        data = await container.campus_service.return_leave(str(leave_id))
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "return_failed", "message": str(exc)}) from exc
    returned_at = datetime.now(timezone.utc).isoformat()
    order.result = {
        **(order.result or {}),
        "returned_at": returned_at,
        "returned_by": user.username,
        "leave_status": data.get("status"),
    }
    order.updated_at = datetime.now(timezone.utc)
    container.workorder_store.save(order)
    container.audit.record(
        AuditEventType.CONFIRMATION.value,
        order.session_id or "",
        order.id,
        {"action": "return_from_leave", "by": user.username, "leave_id": leave_id},
    )
    try:
        if session.owner_id:
            container.notifications.add(
                session.owner_id,
                title="销假完成",
                message="你的请假单已销假，欢迎返校。",
                link="#/workorders",
                dedupe_key=f"{order.id}:returned",
            )
    except Exception:  # noqa: BLE001
        pass
    return {"returned": True, "returned_at": returned_at, "leave_status": data.get("status")}


@router.post("/{workorder_id}/withdraw", summary="学生撤回待审批请假")
def withdraw(
    workorder_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    container = get_container()
    order = container.workorder_store.get(workorder_id)
    if order.status != WorkOrderStatus.AWAITING_APPROVAL:
        raise HTTPException(409, detail={"code": "not_pending", "message": "工单不在待审批状态"})
    try:
        session = container.session_manager.get(order.session_id or "")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(404, detail={"code": "session_not_found", "message": "会话不存在"}) from exc
    if user.role not in {"admin", "auditor"} and session.owner_id != (user.student_id or user.username):
        raise HTTPException(403, detail={"code": "forbidden", "message": "只能撤回自己的申请"})
    order.status = WorkOrderStatus.CANCELLED
    order.result = {**(order.result or {}), "withdrawn": True, "withdrawn_by": user.username}
    order.updated_at = datetime.now(timezone.utc)
    container.workorder_store.save(order)
    container.audit.record(
        AuditEventType.CONFIRMATION.value,
        order.session_id or "",
        order.id,
        {"action": "withdraw", "by": user.username},
    )
    return {"withdrawn": True, "status": order.status.value}


@router.post("/{workorder_id}/approve", summary="审批通过")
async def approve(
    workorder_id: str,
    payload: ApprovalAction,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    return await _act(workorder_id, True, payload.note, user)


@router.post("/{workorder_id}/reject", summary="审批驳回")
async def reject(
    workorder_id: str,
    payload: ApprovalAction,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    return await _act(workorder_id, False, payload.note, user)


async def _act(workorder_id: str, approved: bool, note: str, user: AuthUser) -> dict[str, Any]:
    _staff(user)
    container = get_container()
    order = container.workorder_store.get(workorder_id)
    if not _visible(order, user):
        raise HTTPException(404, detail={"code": "workorder_not_found", "message": "工单不存在"})
    if order.status != WorkOrderStatus.AWAITING_APPROVAL:
        raise HTTPException(409, detail={"code": "not_pending", "message": "工单不在待审批状态"})
    result = await container.engine.resume(
        workorder_id,
        "审批通过" if approved else "审批驳回",
        confirmed=approved,
    )
    container.audit.record(
        AuditEventType.CONFIRMATION.value,
        order.session_id or "",
        order.id,
        {
            "action": "approved" if approved else "rejected",
            "staff": user.username,
            "note": note,
        },
    )
    try:
        session = container.session_manager.get(order.session_id or "")
        if session.owner_id:
            container.notifications.add(
                session.owner_id,
                title="审批结果",
                message=(
                    f"你的请假申请已{'通过' if approved else '驳回'}"
                    + (f"：{note}" if note else "。")
                ),
                link="#/workorders",
                dedupe_key=f"{order.id}:approval",
            )
    except Exception:  # noqa: BLE001
        pass
    return {
        "approved": approved,
        "status": result.workorder.status.value,
        "workorder": result.workorder.model_dump(mode="json"),
    }
