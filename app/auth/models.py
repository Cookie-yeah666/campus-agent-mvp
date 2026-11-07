"""认证相关的 API 模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["student", "counselor", "auditor", "admin"]

ROLE_LABELS: dict[str, str] = {
    "student": "学生",
    "counselor": "辅导员",
    "auditor": "审计员",
    "admin": "管理员",
}


class AuthUser(BaseModel):
    """当前登录用户。"""

    username: str
    name: str
    role: Role
    college: str | None = None
    student_id: str | None = None
    major: str | None = None
    class_name: str | None = None
    cohort: str | None = None
    phone_masked: str | None = None
    status: str | None = None
    anonymous: bool = False

    @property
    def role_label(self) -> str:
        """中文角色名。"""
        return ROLE_LABELS.get(self.role, self.role)


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str | None = Field(default=None, max_length=40)
    student_id: str | None = Field(default=None, max_length=20)
    name: str | None = Field(default=None, max_length=40)
    password: str = Field(min_length=1, max_length=80)


class LoginResponse(BaseModel):
    """登录响应。"""

    token: str
    user: AuthUser
    expires_in: int
