"""工单与审计查询接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.access import can_view_session, can_view_workorder
from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.core.enums import WorkOrderStatus
from app.deps import get_container
from app.models.schema import (
    AuditListResponse,
    WorkOrder,
    WorkOrderListResponse,
)

router = APIRouter(tags=["工单与审计"])


@router.get("/workorders", response_model=WorkOrderListResponse, summary="工单列表")
def list_workorders(
    status: str | None = Query(default=None, description="工单状态筛选"),
    limit: int = Query(default=100, ge=1, le=500),
    user: AuthUser = Depends(get_current_user),
) -> WorkOrderListResponse:
    """按更新时间倒序返回当前角色可见的工单。"""
    container = get_container()
    parsed: WorkOrderStatus | None = None
    if status:
        try:
            parsed = WorkOrderStatus(status)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_status", "message": f"未知工单状态: {status}"},
            ) from exc
    visible = [
        order
        for order in container.workorder_store.list(parsed)
        if can_view_workorder(user, order, container.session_manager)
    ][:limit]
    counts: dict[str, int] = {}
    for order in visible:
        counts[order.status.value] = counts.get(order.status.value, 0) + 1
    return WorkOrderListResponse(items=visible, total=len(visible), counts=counts)


@router.get("/workorders/{workorder_id}", response_model=WorkOrder, summary="工单详情")
def get_workorder(
    workorder_id: str,
    user: AuthUser = Depends(get_current_user),
) -> WorkOrder:
    """返回工单及完整节点历史。"""
    container = get_container()
    order = container.workorder_store.get(workorder_id)
    if not can_view_workorder(user, order, container.session_manager):
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    return order


@router.get(
    "/workorders/{workorder_id}/audit",
    response_model=AuditListResponse,
    summary="工单审计轨迹",
)
def workorder_audit(
    workorder_id: str,
    limit: int = Query(default=500, ge=1, le=2000),
    user: AuthUser = Depends(get_current_user),
) -> AuditListResponse:
    """返回某工单的全部审计事件。"""
    container = get_container()
    order = container.workorder_store.get(workorder_id)
    if not can_view_workorder(user, order, container.session_manager):
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    logs = container.audit.query_workorder(workorder_id, limit=limit)
    return AuditListResponse(items=logs, total=len(logs))


@router.get("/audit/recent", response_model=AuditListResponse, summary="最近审计")
def recent_audit(
    limit: int = Query(default=100, ge=1, le=500),
    user: AuthUser = Depends(get_current_user),
) -> AuditListResponse:
    """返回当前角色可见的最近审计事件。"""
    container = get_container()
    logs = container.audit.recent(limit)
    if user.anonymous or user.role in {"admin", "auditor"}:
        return AuditListResponse(items=logs, total=len(logs))
    visible_ids = {
        session.id
        for session in container.session_manager.list()
        if can_view_session(user, session)
    }
    filtered = [log for log in logs if log.session_id in visible_ids]
    return AuditListResponse(items=filtered, total=len(filtered))


@router.get("/audit/verify", summary="审计哈希链校验")
def verify_audit_chain(
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """仅审计员/管理员可校验；普通工作人员不可见。"""
    if not (user.anonymous or user.role in {"admin", "auditor"}):
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    return get_container().audit.verify_chain()


@router.get(
    "/audit/sessions/{session_id}",
    response_model=AuditListResponse,
    summary="按会话查询审计",
)
def audit_by_session(
    session_id: str,
    limit: int = Query(default=500, ge=1, le=2000),
    user: AuthUser = Depends(get_current_user),
) -> AuditListResponse:
    """按会话 ID 拉取审计轨迹。"""
    container = get_container()
    session = container.session_manager.get(session_id)
    if not can_view_session(user, session):
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    logs = container.audit.query_session(session_id, limit=limit)
    return AuditListResponse(items=logs, total=len(logs))
