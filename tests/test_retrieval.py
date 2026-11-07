"""检索层测试：召回、融合、过滤、改写与评测。"""

from __future__ import annotations

from app.config import Settings
from app.deps import AppContainer
from app.evaluation.dataset import EVAL_QUERIES
from app.retrieval.chunking import chunk_document
from app.retrieval.query_rewriter import QueryRewriter


def test_chunking_keeps_section_metadata(container: AppContainer) -> None:
    """分块应保留文档 ID、章节与文号。"""
    document = container.knowledge.documents[0]
    chunks = chunk_document(
        document,
        min_chars=500,
        max_chars=800,
        overlap=50,
    )
    assert chunks
    assert all(chunk.doc_id == document.id for chunk in chunks)
    assert all(chunk.chapter for chunk in chunks)
    assert all(chunk.doc_number == document.doc_number for chunk in chunks)


def test_hybrid_top1_scholarship(container: AppContainer) -> None:
    """奖学金材料问题应召回对应制度。"""
    bundle = container.retriever.search("奖学金申请需要什么材料")
    assert bundle.results
    assert bundle.results[0].doc_id == "affairs-scholarship"
    assert bundle.results[0].score >= 0.7
    assert all(
        result.score >= bundle.top_score * 0.55 for result in bundle.results
    )


def test_hybrid_top1_card_fee(container: AppContainer) -> None:
    """补卡费用问题应召回校园卡办法并包含金额。"""
    bundle = container.retriever.search("校园卡补办要多少钱")
    top = bundle.results[0]
    assert top.doc_id == "reg-card"
    assert "20 元" in top.content
    assert top.vector_score > 0
    assert top.keyword_score > 0
    assert top.fusion_score > 0


def test_category_filter(container: AppContainer) -> None:
    """类别过滤只返回指定类别。"""
    bundle = container.retriever.search("借阅期限", category_filter="图书馆")
    assert bundle.results
    assert all(result.category == "图书馆" for result in bundle.results)


def test_unknown_query_low_confidence(container: AppContainer) -> None:
    """知识库外的实体应得到低置信度，而不是虚高。"""
    bundle = container.retriever.search("学校附近有什么好吃的火锅")
    assert bundle.top_score < container.settings.low_confidence


def test_rewriter_normalizes_colloquial() -> None:
    """口语化与简称应归一为书面表达。"""
    rewriter = QueryRewriter()
    normalized = rewriter.normalize("补卡咋弄，要啥材料")
    assert "校园卡补办" in normalized
    assert "如何办理" in normalized
    assert "需要哪些材料" in normalized


def test_rewriter_contextual(container: AppContainer) -> None:
    """短追问应生成上下文补全查询。"""
    result = container.retriever.rewriter.rewrite(
        "转专业学生呢",
        context=["转专业需要什么条件"],
    )
    assert result.normalized
    assert result.rewritten
    assert any("转专业需要什么条件" in item for item in result.rewritten)


def test_evaluation_meets_target(container: AppContainer) -> None:
    """内置评测集应达到 Recall@5 与 MRR@5 目标。"""
    report = container.evaluation.run(save_audit=False)
    assert report.dataset_size == len(EVAL_QUERIES)
    assert report.recall_at_5 >= 0.85
    assert report.mrr_at_5 >= 0.70
    assert report.avg_latency_ms < 200
    assert report.by_category
    assert all(item["recall_at_5"] >= 0.8 for item in report.by_category.values())


def test_knowledge_stats(container: AppContainer) -> None:
    """知识库应包含 12 篇文档与四类目。"""
    stats = container.knowledge.stats()
    assert stats["documents"] == 12
    assert stats["chunks"] >= 40
    assert set(container.knowledge.categories()) == {"规章", "教务", "学工", "图书馆"}


def test_settings_defaults() -> None:
    """关键阈值应集中配置且符合设计。"""
    settings = Settings()
    assert 0 < settings.low_confidence < settings.high_confidence < 1
    assert settings.final_top_k == 5
