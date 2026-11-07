"""评测执行器。

当前实现检索层指标（Recall@5、MRR@5、时延与低置信度占比），
对应项目说明书中的“知识库检索可用性”验证项。
"""

from __future__ import annotations

import math
import statistics
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.enums import AuditEventType
from app.evaluation.dataset import EVAL_QUERIES
from app.models.schema import EvaluationQueryResult, EvaluationReport
from app.retrieval.hybrid_retriever import HybridRetriever


class EvaluationRunner:
    """离线检索评测器。"""

    def __init__(
        self,
        retriever: HybridRetriever,
        audit: Any,
        settings: Any,
    ) -> None:
        self._retriever = retriever
        self._audit = audit
        self._settings = settings
        self._latest: EvaluationReport | None = None

    @property
    def latest(self) -> EvaluationReport | None:
        """最近一次评测结果。"""
        return self._latest

    def run(self, *, save_audit: bool = True) -> EvaluationReport:
        """运行全量检索评测。"""
        details: list[EvaluationQueryResult] = []
        latencies: list[float] = []
        for item in EVAL_QUERIES:
            started = time.perf_counter()
            bundle = self._retriever.search(item.query, top_k=5)
            latency = (time.perf_counter() - started) * 1000
            latencies.append(latency)
            retrieved = [result.doc_id for result in bundle.results]
            rank: int | None = None
            for index, doc_id in enumerate(retrieved, start=1):
                if doc_id == item.doc_id:
                    rank = index
                    break
            details.append(
                EvaluationQueryResult(
                    query=item.query,
                    category=item.category,
                    expected_doc_id=item.doc_id,
                    retrieved_doc_ids=retrieved,
                    hit=rank is not None,
                    rank=rank,
                    latency_ms=int(latency),
                )
            )

        total = len(details)
        hits = sum(1 for item in details if item.hit)
        recall = hits / total if total else 0.0
        mrr = (
            sum(1.0 / item.rank for item in details if item.rank)
            / total
            if total
            else 0.0
        )

        by_category: dict[str, dict[str, float]] = {}
        for category in sorted({item.category for item in details}):
            subset = [item for item in details if item.category == category]
            category_hits = sum(1 for item in subset if item.hit)
            category_mrr = sum(
                1.0 / item.rank for item in subset if item.rank
            ) / len(subset)
            by_category[category] = {
                "count": float(len(subset)),
                "recall_at_5": round(category_hits / len(subset), 4),
                "mrr_at_5": round(category_mrr, 4),
            }

        sorted_latencies = sorted(latencies)
        p95_index = max(0, math.ceil(0.95 * len(sorted_latencies)) - 1)
        report = EvaluationReport(
            run_id=f"ev-{uuid.uuid4().hex[:10]}",
            created_at=datetime.now(timezone.utc),
            dataset_size=total,
            recall_at_5=round(recall, 4),
            mrr_at_5=round(mrr, 4),
            avg_latency_ms=round(statistics.fmean(latencies), 2) if latencies else 0.0,
            p95_latency_ms=round(sorted_latencies[p95_index], 2) if latencies else 0.0,
            refusal_rate=round(
                sum(
                    1
                    for item in details
                    if not item.hit
                )
                / total,
                4,
            )
            if total
            else 0.0,
            by_category=by_category,
            details=details,
        )
        self._latest = report
        if save_audit:
            self._audit.record(
                AuditEventType.EVALUATION.value,
                session_id="evaluation",
                payload={
                    "run_id": report.run_id,
                    "dataset_size": report.dataset_size,
                    "recall_at_5": report.recall_at_5,
                    "mrr_at_5": report.mrr_at_5,
                    "avg_latency_ms": report.avg_latency_ms,
                },
            )
        return report
