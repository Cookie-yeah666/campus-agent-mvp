"""无状态 Token 认证。

课程原型使用 HMAC-SHA256 签名的自包含 Token，避免引入 JWT 依赖；
生产环境应替换为统一身份认证（CAS/OAuth2）并接入正式的密钥管理。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from app.auth.models import AuthUser
from app.config import Settings
from app.student_registry import StudentRegistry, mask_phone, normalize_student_id

# 工作人员演示账号；学生账号来自 registry/students.db。
DEMO_ACCOUNTS: tuple[dict[str, Any], ...] = (
    {
        "username": "counselor",
        "password": "counselor123",
        "name": "辅导员演示账号",
        "role": "counselor",
        "college": "计算机科学与技术学院",
        "student_id": None,
    },
    {
        "username": "auditor",
        "password": "auditor123",
        "name": "审计演示账号",
        "role": "auditor",
        "college": None,
        "student_id": None,
    },
    {
        "username": "admin",
        "password": "admin123",
        "name": "系统管理员",
        "role": "admin",
        "college": None,
        "student_id": None,
    },
)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _password_hash(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return _b64encode(digest)


class AuthService:
    """账号、密码与 Token 服务。"""

    def __init__(self, settings: Settings, registry: StudentRegistry | None = None) -> None:
        self._settings = settings
        self._registry = registry
        self._accounts: dict[str, dict[str, Any]] = {}
        self._hashes: dict[str, tuple[bytes, str]] = {}
        for account in DEMO_ACCOUNTS:
            username = account["username"]
            salt = secrets.token_bytes(16)
            self._accounts[username] = dict(account)
            self._hashes[username] = (salt, _password_hash(account["password"], salt))

    @property
    def demo_accounts(self) -> list[dict[str, str]]:
        """返回可展示的演示账号（不含密码哈希）。"""
        return [
            {
                "username": item["username"],
                "name": item["name"],
                "role": item["role"],
                "college": item["college"] or "",
            }
            for item in self._accounts.values()
        ]

    def authenticate_student(
        self,
        student_id: str,
        name: str,
        password: str,
    ) -> AuthUser | None:
        """按名册校验学生：学号 + 姓名 + 学号后六位。"""
        if self._registry is None:
            return None
        normalized_id = normalize_student_id(student_id)
        if normalized_id is None:
            return None
        row = self._registry.lookup(normalized_id)
        if row is None:
            return None
        if str(row.get("name", "")).strip() != name.strip():
            return None
        expected = normalized_id[-6:]
        if not hmac.compare_digest(password, expected):
            return None
        return AuthUser(
            username=normalized_id,
            name=row["name"],
            role="student",
            college=row.get("college"),
            student_id=normalized_id,
            major=row.get("major"),
            class_name=row.get("class_name"),
            cohort=row.get("cohort"),
            phone_masked=mask_phone(row.get("phone")),
            status=row.get("status"),
        )

    def student_login_error(self, student_id: str, name: str, password: str) -> str:
        """给学生登录失败一个可操作的提示，不返回名册中的真实姓名。"""
        if self._registry is None:
            return "学号、姓名或密码错误"
        normalized_id = normalize_student_id(student_id)
        if normalized_id is None:
            return "学号格式不正确，请输入 10 位学号"
        row = self._registry.lookup(normalized_id)
        if row is None:
            return "学号不在名册中，请核对后重试"
        if str(row.get("name", "")).strip() != name.strip():
            return "姓名与名册不一致，请核对姓名用字"
        if not hmac.compare_digest(password, normalized_id[-6:]):
            return "密码不正确，初始密码为学号后六位"
        return "学号、姓名或密码错误"

    def authenticate(self, username: str, password: str) -> AuthUser | None:
        """校验工作人员账号密码，成功返回用户。"""
        key = username.strip()
        account = self._accounts.get(key)
        if account is None:
            return None
        salt, expected = self._hashes[key]
        actual = _password_hash(password, salt)
        if not hmac.compare_digest(actual, expected):
            return None
        return self._user_from_account(account)

    def issue_token(self, user: AuthUser) -> tuple[str, int]:
        """签发 Token，返回 (token, 有效期秒数)。"""
        ttl = max(60, int(self._settings.auth_token_ttl_seconds))
        payload = {
            "sub": user.username,
            "name": user.name,
            "role": user.role,
            "college": user.college,
            "student_id": user.student_id,
            "major": user.major,
            "class_name": user.class_name,
            "cohort": user.cohort,
            "phone_masked": user.phone_masked,
            "status": user.status,
            "iat": int(time.time()),
            "exp": int(time.time()) + ttl,
        }
        encoded = _b64encode(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        signature = _b64encode(
            hmac.new(
                self._settings.auth_secret.encode("utf-8"),
                encoded.encode("ascii"),
                hashlib.sha256,
            ).digest()
        )
        return f"{encoded}.{signature}", ttl

    def verify_token(self, token: str) -> AuthUser | None:
        """校验 Token 签名与过期时间。"""
        try:
            encoded, signature = token.split(".", 1)
            expected = _b64encode(
                hmac.new(
                    self._settings.auth_secret.encode("utf-8"),
                    encoded.encode("ascii"),
                    hashlib.sha256,
                ).digest()
            )
            if not hmac.compare_digest(signature, expected):
                return None
            payload = json.loads(_b64decode(encoded).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        try:
            return AuthUser(
                username=str(payload["sub"]),
                name=str(payload["name"]),
                role=payload["role"],
                college=payload.get("college"),
                student_id=payload.get("student_id"),
                major=payload.get("major"),
                class_name=payload.get("class_name"),
                cohort=payload.get("cohort"),
                phone_masked=payload.get("phone_masked"),
                status=payload.get("status"),
            )
        except (KeyError, ValueError):
            return None

    @staticmethod
    def _user_from_account(account: dict[str, Any]) -> AuthUser:
        return AuthUser(
            username=account["username"],
            name=account["name"],
            role=account["role"],
            college=account.get("college"),
            student_id=account.get("student_id"),
        )


def anonymous_admin() -> AuthUser:
    """测试/关闭认证时使用的匿名管理员。"""
    return AuthUser(
        username="anonymous",
        name="匿名管理员",
        role="admin",
        anonymous=True,
    )
