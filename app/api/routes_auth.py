"""登录与当前用户接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser, LoginRequest, LoginResponse
from app.deps import get_container

router = APIRouter(tags=["认证"])


@router.post("/auth/login", response_model=LoginResponse, summary="登录")
def login(payload: LoginRequest) -> LoginResponse:
    """学生名册登录 / 工作人员演示账号登录。"""
    container = get_container()
    if payload.student_id:
        user = container.auth.authenticate_student(
            payload.student_id,
            payload.name or "",
            payload.password,
        )
        mode = "student"
    elif payload.username:
        user = container.auth.authenticate(payload.username, payload.password)
        mode = "staff"
    else:
        user = None
        mode = "unknown"
    if user is None:
        container.audit.record(
            "auth",
            "auth",
            None,
            {
                "action": "login_failed",
                "mode": mode,
                "username": payload.username,
                "student_id": payload.student_id,
            },
        )
        if payload.student_id:
            message = container.auth.student_login_error(
                payload.student_id,
                payload.name or "",
                payload.password,
            )
        else:
            message = "账号或密码错误"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": message},
        )
    token, ttl = container.auth.issue_token(user)
    container.audit.record(
        "auth",
        "auth",
        None,
        {"action": "login", "mode": mode, "username": user.username, "role": user.role},
    )
    return LoginResponse(token=token, user=user, expires_in=ttl)


@router.get("/auth/me", response_model=AuthUser, summary="当前用户")
def me(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """返回当前 Token 对应的用户。"""
    return user
