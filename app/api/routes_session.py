"""会话管理接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.access import can_view_session
from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.deps import get_container
from app.models.schema import (
    AuditListResponse,
    ChatSession,
    SessionListResponse,
    SessionSummary,
)

router = APIRouter(tags=["会话"])


class SessionCreateRequest(BaseModel):
    """新建会话请求。"""

    title: str | None = Field(default=None, max_length=60)


@router.post(
    "/sessions",
    response_model=ChatSession,
    status_code=status.HTTP_201_CREATED,
    summary="新建会话",
)
def create_session(
    payload: SessionCreateRequest | None = None,
    user: AuthUser = Depends(get_current_user),
) -> ChatSession:
    """创建空会话。"""
    container = get_container()
    return container.session_manager.create(
        payload.title if payload else None,
        owner=user,
    )


@router.get("/sessions", response_model=SessionListResponse, summary="会话列表")
def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: AuthUser = Depends(get_current_user),
) -> SessionListResponse:
    """按更新时间倒序返回当前角色可见的会话。"""
    container = get_container()
    sessions = [
        session
        for session in container.session_manager.list()
        if can_view_session(user, session)
    ]
    sliced = sessions[offset : offset + limit]
    items = [
        SessionSummary(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=len(session.messages),
            current_workflow_id=session.current_workflow_id,
            last_message_preview=(
                session.messages[-1].content[:60] if session.messages else ""
            ),
        )
        for session in sliced
    ]
    return SessionListResponse(items=items, total=len(sessions))


@router.get("/sessions/{session_id}", response_model=ChatSession, summary="会话详情")
def get_session(
    session_id: str,
    user: AuthUser = Depends(get_current_user),
) -> ChatSession:
    """返回会话及全部消息。"""
    session = get_container().session_manager.get(session_id)
    if not can_view_session(user, session):
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    return session


@router.delete("/sessions/{session_id}", summary="删除会话")
def delete_session(
    session_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, bool]:
    """删除会话及其消息文件。"""
    container = get_container()
    session = container.session_manager.get(session_id)
    if not can_view_session(user, session):
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    container.session_manager.delete(session_id)
    return {"deleted": True}


@router.get(
    "/sessions/{session_id}/audit",
    response_model=AuditListResponse,
    summary="会话审计轨迹",
)
def session_audit(
    session_id: str,
    limit: int = Query(default=500, ge=1, le=2000),
    user: AuthUser = Depends(get_current_user),
) -> AuditListResponse:
    """返回会话的完整审计轨迹，用于回放复盘。"""
    container = get_container()
    session = container.session_manager.get(session_id)
    if not can_view_session(user, session):
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    logs = container.audit.query_session(session_id, limit=limit)
    return AuditListResponse(items=logs, total=len(logs))
