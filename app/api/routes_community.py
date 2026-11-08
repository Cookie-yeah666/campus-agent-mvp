"""校园失物招领与学生意见反馈接口。"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.deps import get_container

router = APIRouter(tags=["校园社区"])


class LostFoundCreate(BaseModel):
    kind: Literal["lost", "found"]
    campus: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=1000)
    category: str = Field(default="其他", max_length=30)
    keywords: str = Field(default="", max_length=120)
    place: str = Field(default="", max_length=80)
    contact: str = Field(default="", max_length=80)
    image_data: str = Field(default="", max_length=3_000_000)


class FeedbackCreate(BaseModel):
    category: str = Field(default="其他", max_length=30)
    content: str = Field(min_length=2, max_length=2000)
    anonymous: bool = False


@router.get("/community/lost-found", summary="失物招领列表与匹配")
def list_lost_found(
    campus: str = Query(default="", max_length=40),
    kind: str = Query(default="", max_length=10),
    q: str = Query(default="", max_length=80),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    return get_container().community.list_lost_found(
        user, campus=campus, kind=kind, query=q
    )


@router.post("/community/lost-found", summary="发布失物或招领")
def create_lost_found(
    payload: LostFoundCreate,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    if payload.image_data and not payload.image_data.startswith("data:image/"):
        raise HTTPException(400, detail={"code": "invalid_image", "message": "图片格式不正确"})
    item = get_container().community.create_lost_found(
        user,
        kind=payload.kind,
        campus=payload.campus,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        keywords=payload.keywords,
        place=payload.place,
        contact=payload.contact,
        image_data=payload.image_data,
    )
    return item


@router.post("/community/lost-found/{item_id}/close", summary="标记失物招领已解决")
def close_lost_found(
    item_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    if not get_container().community.close_lost_found(item_id, user):
        raise HTTPException(404, detail={"code": "not_found", "message": "记录不存在或无权限"})
    return {"closed": True}


@router.get("/community/feedback", summary="意见反馈列表")
def list_feedback(
    category: str = Query(default="", max_length=30),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    return get_container().community.list_feedback(user, category=category)


@router.post("/community/feedback", summary="提交意见反馈")
def create_feedback(
    payload: FeedbackCreate,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    return get_container().community.create_feedback(
        user,
        category=payload.category,
        content=payload.content,
        anonymous=payload.anonymous,
    )
