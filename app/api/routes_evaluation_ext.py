"""扩展评测接口：300 silver 检索、引用/拒答、20 条任务。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.deps import get_container
from app.evaluation.extended import (
    QA_DATASET,
    run_generation,
    run_retrieval,
    run_tasks,
)

router = APIRouter(tags=["评测"])
_LATEST: dict[str, dict[str, Any]] = {}


@router.post("/evaluation/extended/run", summary="运行扩展评测")
def run_extended(
    suite: str = Query(default="retrieval", pattern="^(retrieval|generation|task)$"),
    split: str = Query(default="test", pattern="^(dev|test)$"),
) -> dict[str, Any]:
    """运行指定扩展评测套件，并缓存最近一次结果。"""
    container = get_container()
    if suite == "retrieval":
        result = run_retrieval(container.retriever, container.settings, split=split)
    elif suite == "generation":
        result = run_generation(container, container.settings, split=split)
    else:
        result = run_tasks()
    _LATEST[suite] = result
    return result


@router.get("/evaluation/extended/latest", summary="最近扩展评测")
def latest_extended(
    suite: str = Query(default="retrieval", pattern="^(retrieval|generation|task)$"),
) -> dict[str, Any]:
    """返回指定套件最近一次结果。"""
    result = _LATEST.get(suite)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "evaluation_not_run", "message": "该套件尚未运行"},
        )
    return result


@router.get("/evaluation/extended/dataset", summary="扩展评测集信息")
def extended_dataset() -> dict[str, Any]:
    """返回 300 条 silver 集的组成与文件 hash。"""
    manifest_path = QA_DATASET.with_name("qa_300.manifest.json")
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {}
    )
    return {
        "path": str(QA_DATASET),
        "exists": QA_DATASET.exists(),
        "manifest": manifest,
    }
