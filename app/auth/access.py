"""基于角色的数据可见范围。"""

from __future__ import annotations

from typing import Any

from app.auth.models import AuthUser

STAFF_ROLES = {"counselor", "auditor", "admin"}


def is_staff(user: AuthUser) -> bool:
    """是否属于工作人员。"""
    return user.anonymous or user.role in STAFF_ROLES


def can_view_session(user: AuthUser, session: Any) -> bool:
    """会话可见性：学生只看自己，辅导员看本学院，审计/管理员看全部。"""
    if user.anonymous or user.role in {"admin", "auditor"}:
        return True
    owner_id = getattr(session, "owner_id", None)
    owner_college = getattr(session, "owner_college", None)
    if user.role == "student":
        return owner_id == user.student_id
    if user.role == "counselor":
        return owner_id is None or owner_college in (None, user.college)
    return False


def can_view_workorder(user: AuthUser, order: Any, sessions: Any) -> bool:
    """工单可见性取决于所属会话。"""
    if user.anonymous or user.role in {"admin", "auditor"}:
        return True
    session_id = getattr(order, "session_id", None)
    if not session_id:
        return user.role == "counselor"
    try:
        session = sessions.get(session_id)
    except Exception:  # noqa: BLE001 - 会话可能已删除
        return False
    return can_view_session(user, session)


def can_view_student(user: AuthUser, student: Any) -> bool:
    """学生记录可见性。"""
    if user.anonymous or user.role in {"admin", "auditor"}:
        return True
    if user.role == "student":
        return student.get("student_id") == user.student_id
    if user.role == "counselor":
        return student.get("college") == user.college
    return False


def student_scope_college(user: AuthUser, requested: str | None) -> str | None:
    """辅导员强制限定本学院；其他角色使用请求值。"""
    if user.role == "counselor":
        return user.college
    return requested
