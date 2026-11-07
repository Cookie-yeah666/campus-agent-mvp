"""评测接口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.deps import get_container
from app.evaluation.dataset import EVAL_QUERIES
from app.models.schema import EvaluationReport

router = APIRouter(tags=["评测"])


@router.post("/evaluation/run", response_model=EvaluationReport, summary="运行检索评测")
def run_evaluation() -> EvaluationReport:
    """运行内置检索冒烟集，返回 Recall@5、MRR@5 与时延。"""
    return get_container().evaluation.run()


@router.get("/evaluation/latest", response_model=EvaluationReport, summary="最近评测结果")
def latest_evaluation() -> EvaluationReport:
    """返回最近一次评测结果；尚未运行时返回 404。"""
    report = get_container().evaluation.latest
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "evaluation_not_run", "message": "尚未运行评测"},
        )
    return report


@router.get("/evaluation/dataset", summary="评测集")
def evaluation_dataset() -> list[dict[str, Any]]:
    """返回内置评测查询与标准文档。"""
    return [
        {"query": item.query, "category": item.category, "doc_id": item.doc_id}
        for item in EVAL_QUERIES
    ]
