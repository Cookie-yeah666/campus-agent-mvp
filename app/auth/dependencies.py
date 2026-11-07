"""FastAPI 认证依赖。"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import AuthUser
from app.auth.service import anonymous_admin
from app.config import get_settings
from app.deps import get_container

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser:
    """解析 Bearer Token；认证关闭时返回匿名管理员。"""
    settings = get_settings()
    if not settings.auth_enabled:
        return anonymous_admin()
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "请先登录"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_container().auth.verify_token(credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "登录已过期，请重新登录"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*roles: str) -> Callable[..., AuthUser]:
    """角色白名单依赖。"""

    def dependency(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if user.anonymous:
            return user
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "forbidden", "message": "当前角色无权访问该资源"},
            )
        return user

    return dependency
