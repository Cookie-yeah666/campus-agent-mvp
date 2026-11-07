"""健康检查与系统状态。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user, require_roles
from app.auth.models import AuthUser
from app.deps import get_container
from app.models.schema import HealthResponse

router = APIRouter(tags=["系统"])


@router.get("/health", response_model=HealthResponse, summary="健康检查")
def health() -> HealthResponse:
    """返回版本、运行时长、知识库与工单统计。"""
    data = get_container().health()
    return HealthResponse(**data)


@router.get("/system/overview", summary="系统总览")
def overview(
    user: AuthUser = Depends(require_roles("auditor", "admin")),
) -> dict[str, Any]:
    """返回工具、工作流、知识库、工单与审计的总览数据。"""
    del user
    return get_container().overview()


@router.get("/tools", summary="工具列表")
def list_tools(
    user: AuthUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """返回全部已注册工具的 JSON Schema。"""
    del user
    container = get_container()
    return [definition.model_dump() for definition in container.tool_registry.definitions()]
