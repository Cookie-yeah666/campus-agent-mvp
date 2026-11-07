"""学生名册查询接口。

名册是独立于演示数据的持久化 SQLite 库；API 只返回脱敏后的字段，
原始手机号不离开服务端。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.access import can_view_student
from app.auth.dependencies import get_current_user, require_roles
from app.auth.models import AuthUser
from app.deps import get_container

router = APIRouter(tags=["学生库"])


@router.get("/students/stats", summary="学生库统计")
def student_stats(
    user: AuthUser = Depends(require_roles("counselor", "auditor", "admin")),
) -> dict[str, Any]:
    """返回总人数、学院/届/班级数、状态分布与最近导入批次。"""
    del user
    return get_container().student_registry.stats()


@router.get("/students/imports", summary="学生库导入批次")
def student_imports(
    limit: int = Query(default=10, ge=1, le=50),
    user: AuthUser = Depends(require_roles("counselor", "auditor", "admin")),
) -> dict[str, Any]:
    """返回最近的导入批次，便于追溯数据来源。"""
    del user
    items = get_container().student_registry.imports(limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/students", summary="学生名册分页检索")
def list_students(
    college: str | None = Query(default=None),
    cohort: str | None = Query(default=None),
    major: str | None = Query(default=None),
    class_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: AuthUser = Depends(require_roles("counselor", "auditor", "admin")),
) -> dict[str, Any]:
    """按学院、届、专业、班级、状态与关键词筛选。"""
    registry = get_container().student_registry
    if user.role == "counselor":
        college = user.college
    rows, total = registry.search(
        college=college,
        cohort=cohort,
        major=major,
        class_name=class_name,
        status=status,
        query=q,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [registry.public_student(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/students/{student_id}", summary="按学号查询学生")
def get_student(
    student_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    """按学号查询名册详情（手机号脱敏）。"""
    registry = get_container().student_registry
    row = registry.lookup(student_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "student_not_found"})
    public = registry.public_student(row)
    if not can_view_student(user, public):
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    return public
