"""扩展评测 CLI。

示例：
    python scripts/evaluate.py --suite retrieval --split test
    python scripts/evaluate.py --suite all --output reports/eval-silver.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.deps import get_container
from app.evaluation.extended import run_all, run_generation, run_retrieval, run_tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="知行扩展评测")
    parser.add_argument(
        "--suite",
        choices=["retrieval", "generation", "task", "all"],
        default="retrieval",
    )
    parser.add_argument("--split", choices=["dev", "test"], default="test")
    parser.add_argument("--output", default=None, help="报告 JSON 路径")
    args = parser.parse_args()

    container = get_container()
    settings = container.settings
    if args.suite == "retrieval":
        result = {"retrieval": run_retrieval(container.retriever, settings, split=args.split)}
    elif args.suite == "generation":
        result = {"generation": run_generation(container, settings, split=args.split)}
    elif args.suite == "task":
        result = {"task": run_tasks()}
    else:
        result = run_all(container, settings, split=args.split)

    print(json.dumps(_summary(result), ensure_ascii=False, indent=2))
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"report -> {path}")


def _summary(result: dict) -> dict:
    summary: dict = {}
    retrieval = result.get("retrieval")
    if retrieval:
        summary["retrieval"] = {
            "n": retrieval["n"],
            "answerable_n": retrieval["answerable_n"],
            "recall_at_5": retrieval["recall_at_5"],
            "recall_at_5_ci": retrieval["recall_at_5_ci"],
            "mrr_at_5": retrieval["mrr_at_5"],
            "ndcg_at_5": retrieval["ndcg_at_5"],
            "hard_negative_fpr": retrieval["hard_negative_fpr"],
            "negative_answer_rate": retrieval["negative_answer_rate"],
        }
    generation = result.get("generation")
    if generation:
        summary["generation"] = {
            "answerable_n": generation["answerable_n"],
            "unanswerable_n": generation["unanswerable_n"],
            "citation_presence_rate": generation["citation_presence_rate"],
            "citation_gold_hit_rate": generation["citation_gold_hit_rate"],
            "refusal_accuracy": generation["refusal_accuracy"],
            "false_answer_rate": generation["false_answer_rate"],
            "mode": generation["mode"],
        }
    task = result.get("task")
    if task:
        summary["task"] = {
            "n": task["n"],
            "passed": task["passed"],
            "success_rate": task["success_rate"],
            "success_rate_ci": task["success_rate_ci"],
            "avg_turns": task["avg_turns"],
            "handoff_rate": task["handoff_rate"],
            "duplicate_new_orders": task["duplicate_new_orders"],
        }
    return summary


if __name__ == "__main__":
    main()
