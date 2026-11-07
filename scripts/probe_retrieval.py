"""临时脚本：打印典型问题的检索分数，用于校准阈值。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.knowledge.loader import KnowledgeBase  # noqa: E402
from app.retrieval.hybrid_retriever import HybridRetriever  # noqa: E402

QUERIES = [
    "奖学金申请需要什么材料",
    "校园卡补办要多少钱",
    "转专业需要什么条件",
    "转专业学生呢",
    "图书馆借书能借多久",
    "请假三天找谁审批",
    "国家助学金一年多少钱",
    "考试作弊会被怎么处理",
    "选课什么时候开始",
    "门禁几点关门",
    "自习室怎么预约",
    "校外怎么访问电子资源",
    "课程不及格怎么办",
    "学校附近有什么好吃的火锅",
    "在吗",
    "帮我写一首诗",
]


def main() -> None:
    settings = Settings()
    knowledge = KnowledgeBase(settings)
    retriever = HybridRetriever(knowledge, settings)
    print("KB", knowledge.stats(), knowledge.categories())
    for query in QUERIES:
        bundle, rewrites = retriever.search_for_qa(query, context=["转专业需要什么条件"])
        top = bundle.results[0] if bundle.results else None
        print(f"\nQ: {query}")
        print(f"  score={bundle.top_score:.3f} rewrites={rewrites}")
        if top:
            print(f"  top={top.doc_id} {top.chapter} conf={top.score:.3f} cov={top.coverage:.3f} "
                  f"vec={top.vector_score:.3f} bm25={top.keyword_score:.2f}")
            for result in bundle.results[1:4]:
                print(f"    - {result.doc_id} {result.score:.3f}")


if __name__ == "__main__":
    main()
