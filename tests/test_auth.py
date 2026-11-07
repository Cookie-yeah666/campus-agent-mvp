"""认证与 RBAC 的单元测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.auth.access import can_view_session, can_view_student
from app.auth.service import AuthService
from app.config import Settings
from app.student_registry import StudentRegistry


def make_auth(registry: StudentRegistry | None = None) -> AuthService:
    return AuthService(
        Settings(
            auth_secret="test-secret",
            auth_token_ttl_seconds=3600,
        ),
        registry,
    )


def make_student_auth(tmp_path: Path) -> AuthService:
    registry = StudentRegistry(tmp_path / "registry" / "students.db")
    registry.upsert_batch(
        [
            {
                "student_id": "2527405999",
                "name": "测试学生",
                "major": "计算机科学与技术",
                "class_name": "计25测试班",
                "phone": "13800138000",
                "gender": "女",
                "dorm_building": "本9",
                "dorm_room": "101",
                "campus": None,
                "status": "active",
                "notes": None,
                "source_row": 2,
            }
        ],
        source_file="test.xlsx",
        source_sha256="test",
        college="计算机科学与技术学院",
        cohort="2025",
    )
    return make_auth(registry)


def test_login_and_token_roundtrip() -> None:
    auth = make_auth()
    user = auth.authenticate("admin", "admin123")
    assert user is not None
    assert user.role == "admin"

    token, ttl = auth.issue_token(user)
    assert ttl == 3600
    decoded = auth.verify_token(token)
    assert decoded is not None
    assert decoded.username == "admin"
    assert decoded.role == "admin"


def test_wrong_password_and_tampered_token(tmp_path: Path) -> None:
    auth = make_auth()
    assert auth.authenticate("admin", "wrong") is None
    student_auth = make_student_auth(tmp_path)
    user = student_auth.authenticate_student("2527405999", "测试学生", "405999")
    assert user is not None
    assert student_auth.authenticate_student("2527405999", "错名", "405999") is None
    assert student_auth.authenticate_student("2527405999", "测试学生", "000000") is None
    token, _ = student_auth.issue_token(user)
    assert student_auth.verify_token(token + "x") is None


def test_student_only_sees_own_session_and_record(tmp_path: Path) -> None:
    auth = make_student_auth(tmp_path)
    student = auth.authenticate_student("2527405999", "测试学生", "405999")
    counselor = auth.authenticate("counselor", "counselor123")
    assert student is not None and counselor is not None

    own = SimpleNamespace(owner_id="2527405999", owner_college="计算机科学与技术学院")
    other = SimpleNamespace(owner_id="2527405002", owner_college="计算机科学与技术学院")
    assert can_view_session(student, own) is True
    assert can_view_session(student, other) is False
    assert can_view_session(counselor, other) is True

    assert can_view_student(
        student,
        {"student_id": "2527405999", "college": "计算机科学与技术学院"},
    )
    assert not can_view_student(
        student,
        {"student_id": "2527405002", "college": "计算机科学与技术学院"},
    )
