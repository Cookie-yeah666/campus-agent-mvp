"""扩展评测：300 条 silver 检索、引用/拒答、20 条办事任务。

这不是人工金标。silver 集用于发现回归和暴露薄弱点；正式论文结论
需要在人工抽检/复核后再使用。
"""

from __future__ import annotations

import asyncio
import json
import math
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.qa_agent import QAAgent
from app.config import BASE_DIR, Settings
from app.deps import build_container
from app.llm.mock_llm import MockLLM
from app.models.schema import ChatRequest, ChatSession, ConfirmRequest
from app.retrieval.hybrid_retriever import HybridRetriever

DATASET_DIR = Path(__file__).resolve().parent / "datasets"
QA_DATASET = DATASET_DIR / "qa_300.jsonl"
TASK_DATASET = DATASET_DIR / "tasks_20.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% 置信区间。"""
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)


def ndcg_at_k(rank: int | None, k: int = 5) -> float:
    """单相关文档的 nDCG@k。"""
    if not rank or rank > k:
        return 0.0
    return 1.0 / math.log2(rank + 1)


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return round(ordered[index], 2)


def load_qa(split: str | None = None) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in QA_DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if split:
        rows = [row for row in rows if row.get("split") == split]
    return rows


class _NullAudit:
    def record(self, *args: Any, **kwargs: Any) -> None:
        return


# ---------------------------------------------------------------------------
# 检索
# ---------------------------------------------------------------------------
def run_retrieval(
    retriever: HybridRetriever,
    settings: Settings,
    *,
    split: str = "test",
) -> dict[str, Any]:
    rows = load_qa(split)
    details: list[dict[str, Any]] = []
    latencies: list[float] = []
    for row in rows:
        started = time.perf_counter()
        bundle = retriever.search(row["question"], top_k=5)
        latency = (time.perf_counter() - started) * 1000
        latencies.append(latency)
        retrieved = [item.doc_id for item in bundle.results]
        gold = set(row.get("gold_doc_ids") or [])
        rank = next((i for i, doc_id in enumerate(retrieved, 1) if doc_id in gold), None)
        hard = set(row.get("hard_negatives") or [])
        hard_hit = any(doc_id in hard for doc_id in retrieved)
        answerable = row.get("answerability") == "answerable"
        negative_answer = (not answerable) and bundle.top_score >= settings.low_confidence
        details.append(
            {
                "id": row["id"],
                "query": row["question"],
                "category": row["category"],
                "answerability": row.get("answerability"),
                "gold": sorted(gold),
                "retrieved": retrieved,
                "rank": rank,
                "hit": rank is not None,
                "ndcg": round(ndcg_at_k(rank), 4),
                "hard_negative_hit": hard_hit,
                "negative_answer": negative_answer,
                "top_score": round(bundle.top_score, 4),
                "latency_ms": round(latency, 2),
            }
        )

    answerable_details = [item for item in details if item["answerability"] == "answerable"]
    negative_details = [item for item in details if item["answerability"] == "unanswerable"]
    n = len(answerable_details)
    hits = sum(1 for item in answerable_details if item["hit"])
    recall = hits / n if n else 0.0
    mrr = sum(1.0 / item["rank"] for item in answerable_details if item["rank"]) / n if n else 0.0
    ndcg = sum(item["ndcg"] for item in answerable_details) / n if n else 0.0
    hard_fpr = (
        sum(1 for item in answerable_details if item["hard_negative_hit"]) / n if n else 0.0
    )
    negative_rate = (
        sum(1 for item in negative_details if item["negative_answer"]) / len(negative_details)
        if negative_details
        else 0.0
    )

    by_category: dict[str, dict[str, Any]] = {}
    for category in sorted({item["category"] for item in answerable_details}):
        subset = [item for item in answerable_details if item["category"] == category]
        by_category[category] = {
            "n": len(subset),
            "recall_at_5": round(sum(1 for item in subset if item["hit"]) / len(subset), 4),
            "mrr_at_5": round(
                sum(1.0 / item["rank"] for item in subset if item["rank"]) / len(subset), 4
            ),
        }

    recall_ci = wilson_interval(hits, n)
    return {
        "suite": "retrieval_300",
        "dataset": {"name": "qa_300_silver", "split": split, "total": len(rows)},
        "created_at": now_iso(),
        "run_id": f"ev300-{uuid.uuid4().hex[:8]}",
        "n": len(rows),
        "answerable_n": n,
        "unanswerable_n": len(negative_details),
        "recall_at_5": round(recall, 4),
        "recall_at_5_ci": list(recall_ci),
        "mrr_at_5": round(mrr, 4),
        "ndcg_at_5": round(ndcg, 4),
        "hit_at_1": round(
            sum(1 for item in answerable_details if item["rank"] == 1) / n if n else 0.0, 4
        ),
        "hard_negative_fpr": round(hard_fpr, 4),
        "negative_answer_rate": round(negative_rate, 4),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "p95_latency_ms": p95(latencies),
        "by_category": by_category,
        "details": details,
        "review_status": "silver",
        "note": "240 条同义改写 + 60 条越界；需人工抽检后再作为论文金标。",
    }


# ---------------------------------------------------------------------------
# 引用 / 拒答
# ---------------------------------------------------------------------------
REFUSAL_MARKERS = ("没有找到可靠的校内依据", "超出校园服务", "转人工咨询", "抱歉")


async def _run_generation(
    qa: QAAgent,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for row in rows:
        started = time.perf_counter()
        session = ChatSession(
            id=f"cs-eval-{uuid.uuid4().hex[:8]}",
            title="evaluation",
        )
        reply = await qa.handle(session, row["question"], history=[])
        latency = (time.perf_counter() - started) * 1000
        content = reply.content or ""
        refused = any(marker in content for marker in REFUSAL_MARKERS)
        citations = [citation.doc_id for citation in (reply.citations or [])]
        gold = set(row.get("gold_doc_ids") or [])
        results.append(
            {
                "id": row["id"],
                "query": row["question"],
                "category": row["category"],
                "answerability": row.get("answerability"),
                "refused": refused,
                "citation_count": len(citations),
                "citation_docs": citations,
                "citation_present": bool(citations),
                "citation_gold_hit": bool(gold & set(citations)),
                "latency_ms": round(latency, 2),
                "answer_preview": content[:160],
            }
        )
    return results


def run_generation(
    container: Any,
    settings: Settings,
    *,
    split: str = "test",
    answerable_limit: int = 60,
    unanswerable_limit: int = 60,
) -> dict[str, Any]:
    rows = load_qa(split)
    answerable = [row for row in rows if row["answerability"] == "answerable"][:answerable_limit]
    unanswerable = [row for row in rows if row["answerability"] == "unanswerable"][
        :unanswerable_limit
    ]
    eval_settings = settings.model_copy(
        update={"llm_simulate_delay": False, "tool_simulate_delay": False}
    )
    qa = QAAgent(
        MockLLM(eval_settings),
        container.retriever,
        container.knowledge,
        _NullAudit(),
        eval_settings,
        container.logger,
    )
    details = asyncio.run(_run_generation(qa, answerable + unanswerable))
    positive = [item for item in details if item["answerability"] == "answerable"]
    negative = [item for item in details if item["answerability"] == "unanswerable"]
    positive_n = len(positive)
    negative_n = len(negative)
    citation_present = sum(1 for item in positive if item["citation_present"]) / positive_n
    citation_gold = sum(1 for item in positive if item["citation_gold_hit"]) / positive_n
    false_refusal = sum(1 for item in positive if item["refused"]) / positive_n
    refused_negative = sum(1 for item in negative if item["refused"]) / negative_n
    return {
        "suite": "generation",
        "dataset": {"name": "qa_300_silver", "split": split, "sampled": len(details)},
        "created_at": now_iso(),
        "run_id": f"evgen-{uuid.uuid4().hex[:8]}",
        "mode": "mock",
        "answerable_n": positive_n,
        "unanswerable_n": negative_n,
        "citation_presence_rate": round(citation_present, 4),
        "citation_gold_hit_rate": round(citation_gold, 4),
        "false_refusal_rate": round(false_refusal, 4),
        "refusal_accuracy": round(refused_negative, 4),
        "false_answer_rate": round(1 - refused_negative, 4),
        "avg_citations": round(
            sum(item["citation_count"] for item in positive) / positive_n if positive_n else 0.0,
            2,
        ),
        "avg_latency_ms": round(
            sum(item["latency_ms"] for item in details) / len(details) if details else 0.0, 2
        ),
        "details": details,
        "review_status": "silver",
        "note": "MockLLM 下只评引用存在性/拒答/引用文档命中，不代表真实生成质量。",
    }


# ---------------------------------------------------------------------------
# 办事任务
# ---------------------------------------------------------------------------
TASK_SCENARIOS: tuple[dict[str, Any], ...] = (
    {"id": "success-01", "kind": "success", "student": "2025001011", "campus": "天赐庄"},
    {"id": "success-02", "kind": "success", "student": "2025001002", "campus": "独墅湖"},
    {"id": "success-03", "kind": "success", "student": "2025001008", "campus": "独墅湖"},
    {"id": "success-04", "kind": "success", "student": "2025001014", "campus": "独墅湖"},
    {"id": "success-05", "kind": "success", "student": "2025001016", "campus": "独墅湖"},
    {"id": "success-06", "kind": "success", "student": "2025001019", "campus": "独墅湖"},
    {"id": "auto-loss-01", "kind": "success", "student": "2025001004", "campus": "天赐庄"},
    {"id": "auto-loss-02", "kind": "success", "student": "2025001006", "campus": "独墅湖"},
    {"id": "auto-loss-03", "kind": "success", "student": "2025001012", "campus": "独墅湖"},
    {"id": "arrears-01", "kind": "arrears", "student": "2025001003", "campus": "阳澄湖"},
    {"id": "arrears-02", "kind": "arrears", "student": "2025001010", "campus": "独墅湖"},
    {"id": "timeout-01", "kind": "timeout", "student": "2025000999", "campus": "天赐庄"},
    {"id": "timeout-02", "kind": "timeout", "student": "2025000999", "campus": "独墅湖"},
    {"id": "invalid-01", "kind": "invalid", "student": "2025009999", "campus": "独墅湖"},
    {"id": "invalid-02", "kind": "invalid", "student": "2025009999", "campus": "天赐庄"},
    {"id": "cancel-01", "kind": "cancel", "student": "2025001001", "campus": "天赐庄"},
    {"id": "cancel-02", "kind": "cancel", "student": "2025001011", "campus": "天赐庄"},
    {"id": "success-07", "kind": "success", "student": "2025001009", "campus": "天赐庄"},
    {"id": "success-08", "kind": "success", "student": "2025001013", "campus": "独墅湖"},
    {"id": "idempotency-01", "kind": "idempotency", "student": "2025001002", "campus": "独墅湖"},
)


def _task_settings(root: Path) -> Settings:
    return Settings(
        data_dir=root / "data",
        student_registry_dir=root / "registry",
        auth_enabled=False,
        llm_simulate_delay=False,
        tool_simulate_delay=False,
    )


async def _run_one_task(scenario: dict[str, Any], root: Path) -> dict[str, Any]:
    container = build_container(_task_settings(root))
    session = container.session_manager.create()
    turns = 0
    first = await container.chat_service.send(
        ChatRequest(session_id=session.id, message="我要补办校园卡")
    )
    turns += 1
    second = await container.chat_service.send(
        ChatRequest(
            session_id=session.id,
            message=f"{scenario['student']} {scenario['campus']}",
        )
    )
    turns += 1
    status = second.workorder.status.value if second.workorder else "missing"
    receipt = second.workorder.receipt_number if second.workorder else ""
    duplicate = False
    duplicated_orders = 0

    if scenario["kind"] in {"success", "cancel"}:
        action = "confirm" if scenario["kind"] == "success" else "cancel"
        final = await container.chat_service.confirm(
            session.id, ConfirmRequest(action=action)
        )
        turns += 1
        status = final.workorder.status.value if final.workorder else status
        receipt = final.workorder.receipt_number if final.workorder else receipt
    elif scenario["kind"] == "idempotency":
        first_final = await container.chat_service.confirm(
            session.id, ConfirmRequest(action="confirm")
        )
        turns += 1
        first_receipt = first_final.workorder.receipt_number if first_final.workorder else ""
        before = container.workorder_store.count()
        second_session = container.session_manager.create()
        await container.chat_service.send(
            ChatRequest(session_id=second_session.id, message="我要补办校园卡")
        )
        await container.chat_service.send(
            ChatRequest(
                session_id=second_session.id,
                message=f"{scenario['student']} {scenario['campus']}",
            )
        )
        duplicate_response = await container.chat_service.confirm(
            second_session.id, ConfirmRequest(action="confirm")
        )
        turns += 3
        after = container.workorder_store.count()
        duplicate = bool(
            duplicate_response.workorder
            and duplicate_response.workorder.receipt_number == first_receipt
        )
        duplicated_orders = max(0, after - before)
        status = duplicate_response.workorder.status.value if duplicate_response.workorder else status
        receipt = first_receipt

    expected = {
        "success": "completed",
        "arrears": "failed",
        "timeout": "transferred_human",
        "invalid": "failed",
        "cancel": "cancelled",
        "idempotency": "completed",
    }[scenario["kind"]]
    passed = status == expected
    if scenario["kind"] == "idempotency":
        passed = passed and duplicate and duplicated_orders == 0
    result = {
        "id": scenario["id"],
        "kind": scenario["kind"],
        "student": scenario["student"],
        "campus": scenario["campus"],
        "expected": expected,
        "actual": status,
        "passed": passed,
        "turns": turns,
        "receipt": receipt,
        "duplicate": duplicate,
        "new_orders_on_duplicate": duplicated_orders,
    }
    del first
    return result


def run_tasks(*, limit: int | None = None) -> dict[str, Any]:
    scenarios = list(TASK_SCENARIOS)[:limit] if limit else list(TASK_SCENARIOS)
    runtime = BASE_DIR / "runtime_work"
    runtime.mkdir(parents=True, exist_ok=True)
    root = runtime / f"eval-tasks-{uuid.uuid4().hex[:8]}"
    root.mkdir()
    try:
        details = [
            asyncio.run(_run_one_task(scenario, root / scenario["id"]))
            for scenario in scenarios
        ]
    finally:
        shutil.rmtree(root, ignore_errors=True)

    passed = sum(1 for item in details if item["passed"])
    total = len(details)
    success_rate = passed / total if total else 0.0
    handoffs = sum(1 for item in details if item["actual"] == "transferred_human")
    duplicate_new = sum(item["new_orders_on_duplicate"] for item in details)
    return {
        "suite": "task_20",
        "created_at": now_iso(),
        "run_id": f"evtask-{uuid.uuid4().hex[:8]}",
        "n": total,
        "passed": passed,
        "success_rate": round(success_rate, 4),
        "success_rate_ci": list(wilson_interval(passed, total)),
        "avg_turns": round(sum(item["turns"] for item in details) / total, 2) if total else 0.0,
        "handoff_rate": round(handoffs / total, 4) if total else 0.0,
        "duplicate_new_orders": duplicate_new,
        "details": details,
        "note": "20 条任务均为独立临时数据目录；使用模拟学号与 Mock 业务系统。",
    }


def run_all(container: Any, settings: Settings, *, split: str = "test") -> dict[str, Any]:
    return {
        "retrieval": run_retrieval(container.retriever, settings, split=split),
        "generation": run_generation(container, settings, split=split),
        "task": run_tasks(),
    }
