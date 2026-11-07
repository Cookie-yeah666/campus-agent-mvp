"""人工坐席：待认领队列、认领、办结。"""

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

router = APIRouter(prefix="/handoff", tags=["人工坐席"])


def _staff(user: AuthUser) -> None:
    if user.role not in {"counselor", "auditor", "admin"}:
        raise HTTPException(403, detail={"code": "staff_only", "message": "仅工作人员可用"})


def _visible_order(order: Any, user: AuthUser) -> bool:
    if user.role in {"auditor", "admin"}:
        return True
    container = get_container()
    try:
        session = container.session_manager.get(order.session_id or "")
    except Exception:  # noqa: BLE001
        return False
    return can_view_session(user, session)


@router.get("/queue", summary="待认领队列")
def queue(user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    _staff(user)
    container = get_container()
    orders = [
        order
        for order in container.workorder_store.list(WorkOrderStatus.TRANSFERRED_HUMAN)
        if _visible_order(order, user)
    ]
    items = []
    for order in orders:
        session = None
        try:
            session = container.session_manager.get(order.session_id or "")
        except Exception:  # noqa: BLE001
            pass
        items.append(
            {
                "id": order.id,
                "workflow_type": order.workflow_type,
                "status": order.status.value,
                "student_id": order.user_inputs.get("student_id"),
                "campus": order.user_inputs.get("campus"),
                "reason": order.handoff_reason or order.error_message or "转人工",
                "assignee_id": order.assignee_id,
                "handoff_at": order.handoff_at.isoformat() if order.handoff_at else None,
                "updated_at": order.updated_at.isoformat(),
                "session_id": order.session_id,
                "session_title": session.title if session else "",
                "owner_id": session.owner_id if session else None,
                "owner_college": session.owner_college if session else None,
                "last_message": session.messages[-1].content if session and session.messages else "",
            }
        )
    return {"items": items, "count": len(items)}


class ClaimRequest(BaseModel):
    pass


class ResolveRequest(BaseModel):
    note: str = Field(min_length=1, max_length=2000)
    result: str = Field(default="completed", pattern="^(completed|cancelled)$")


@router.post("/{workorder_id}/claim", summary="认领工单")
def claim(workorder_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, Any]:
    _staff(user)
    container = get_container()
    order = container.workorder_store.get(workorder_id)
    if not _visible_order(order, user):
        raise HTTPException(404, detail={"code": "workorder_not_found", "message": "工单不存在"})
    if order.status != WorkOrderStatus.TRANSFERRED_HUMAN:
        raise HTTPException(409, detail={"code": "not_pending", "message": "工单不在待认领状态"})
    if order.assignee_id and order.assignee_id != user.username:
        raise HTTPException(409, detail={"code": "already_claimed", "message": "已被其他坐席认领"})
    order.assignee_id = user.username
    order.updated_at = datetime.now(timezone.utc)
    container.workorder_store.save(order)
    container.audit.record(
        AuditEventType.HANDOFF.value,
        order.session_id or "",
        order.id,
        {"action": "claim", "assignee": user.username},
    )
    return {"claimed": True, "assignee_id": user.username}


@router.post("/{workorder_id}/resolve", summary="办结工单")
def resolve(
    workorder_id: str,
    payload: ResolveRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    _staff(user)
    container = get_container()
    order = container.workorder_store.get(workorder_id)
    if not _visible_order(order, user):
        raise HTTPException(404, detail={"code": "workorder_not_found", "message": "工单不存在"})
    if order.status != WorkOrderStatus.TRANSFERRED_HUMAN:
        raise HTTPException(409, detail={"code": "not_pending", "message": "工单不在待处理状态"})
    order.assignee_id = user.username
    order.status = (
        WorkOrderStatus.COMPLETED
        if payload.result == "completed"
        else WorkOrderStatus.CANCELLED
    )
    order.resolved_at = datetime.now(timezone.utc)
    order.updated_at = datetime.now(timezone.utc)
    order.result = {
        **(order.result or {}),
        "resolution": payload.note,
        "resolved_by": user.username,
        "resolved_at": order.resolved_at.isoformat(),
    }
    container.workorder_store.save(order)
    container.audit.record(
        AuditEventType.HANDOFF.value,
        order.session_id or "",
        order.id,
        {"action": "resolve", "assignee": user.username, "result": payload.result, "note": payload.note},
    )
    try:
        session = container.session_manager.get(order.session_id or "")
        if session.owner_id:
            container.notifications.add(
                session.owner_id,
                title="人工处理完成",
                message=f"你的工单已由工作人员处理：{payload.note}",
                link="#/workorders",
                dedupe_key=f"{order.id}:resolved",
            )
    except Exception:  # noqa: BLE001
        pass
    return {"resolved": True, "status": order.status.value}
