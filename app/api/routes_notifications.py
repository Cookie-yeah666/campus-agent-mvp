"""站内通知接口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.deps import get_container

router = APIRouter(prefix="/notifications", tags=["通知"])


def _owner(user: AuthUser) -> str:
    return user.student_id or user.username


@router.get("", summary="我的通知")
def list_notifications(
    limit: int = Query(default=20, ge=1, le=50),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    container = get_container()
    owner = _owner(user)
    return {
        "items": container.notifications.list(owner, limit),
        "unread": container.notifications.unread_count(owner),
    }


@router.post("/read", summary="标记已读")
def mark_read(
    notification_id: str | None = None,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    owner = _owner(user)
    changed = get_container().notifications.mark_read(owner, notification_id)
    return {"changed": changed, "unread": get_container().notifications.unread_count(owner)}
