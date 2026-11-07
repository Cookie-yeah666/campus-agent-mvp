"""对话接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth.access import can_view_session
from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.core.enums import WorkOrderStatus
from app.deps import get_container
from app.models.schema import ChatMessage, ChatRequest, ChatResponse, ConfirmRequest

router = APIRouter(tags=["对话"])


def _notify_workorder(workorder) -> None:
    if workorder is None:
        return
    container = get_container()
    try:
        session = container.session_manager.get(workorder.session_id or "")
    except Exception:  # noqa: BLE001
        return
    owner = session.owner_id
    if not owner:
        return
    if workorder.status == WorkOrderStatus.TRANSFERRED_HUMAN:
        container.notifications.add(
            owner,
            title="工单已转人工",
            message=f"你的{workorder.workflow_type}工单已转人工，工作人员会尽快处理。",
            link="#/workorders",
            dedupe_key=f"{workorder.id}:handoff",
        )
    elif workorder.status == WorkOrderStatus.COMPLETED:
        container.notifications.add(
            owner,
            title="工单已完成",
            message=f"你的{workorder.workflow_type}工单已完成，回执：{workorder.receipt_number or '—'}。",
            link="#/workorders",
            dedupe_key=f"{workorder.id}:completed",
        )


@router.post("/chat/send", response_model=ChatResponse, summary="发送消息")
async def send_message(
    payload: ChatRequest,
    user: AuthUser = Depends(get_current_user),
) -> ChatResponse:
    """核心对话接口：意图路由 → Agent 处理 → 落库/审计 → 返回。"""
    container = get_container()
    if payload.session_id:
        session = container.session_manager.get(payload.session_id)
        if not can_view_session(user, session):
            raise HTTPException(status_code=403, detail={"code": "forbidden"})
    response = await container.chat_service.send(payload, owner=user)
    _notify_workorder(response.workorder)
    return response


@router.get(
    "/chat/sessions/{session_id}/messages",
    response_model=list[ChatMessage],
    summary="会话消息",
)
def get_messages(
    session_id: str,
    user: AuthUser = Depends(get_current_user),
) -> list[ChatMessage]:
    """返回某会话的全部消息。"""
    container = get_container()
    session = container.session_manager.get(session_id)
    if not can_view_session(user, session):
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    return container.chat_service.history(session_id)


@router.post(
    "/chat/sessions/{session_id}/confirm",
    response_model=ChatResponse,
    summary="确认/取消办事节点",
)
async def confirm_workorder(
    session_id: str,
    payload: ConfirmRequest,
    user: AuthUser = Depends(get_current_user),
) -> ChatResponse:
    """提交办事流程确认节点的确认或取消动作。"""
    container = get_container()
    session = container.session_manager.get(session_id)
    if not can_view_session(user, session):
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    response = await container.chat_service.confirm(session_id, payload)
    _notify_workorder(response.workorder)
    return response
