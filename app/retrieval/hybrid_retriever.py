"""混合检索：向量召回 + 关键词召回 + RRF 融合 + IDF 覆盖率校准。

最终置信度 ``score`` 由三部分加权：
- ``coverage``：查询关键概念被分块覆盖的比例（主信号，0~1）；
- ``vector_norm``：余弦相似度归一化；
- ``keyword_norm``：BM25 得分归一化。
RRF 只负责候选排序，不直接作为置信度，避免分数不可解释。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.config import Settings
from app.knowledge.loader import KnowledgeBase
from app.models.domain import RetrievalResult
from app.retrieval.keyword_search import BM25Index
from app.retrieval.query_rewriter import QueryRewriter
from app.retrieval.tokenizer import tokenize
from app.retrieval.vector_search import TfidfVectorIndex


@dataclass
class RetrievalBundle:
    """一次混合检索的完整输出，便于轨迹面板展示。"""

    query: str
    normalized_query: str
    results: list[RetrievalResult] = field(default_factory=list)
    vector_candidates: int = 0
    keyword_candidates: int = 0
    latency_ms: int = 0
    rewritten_queries: list[str] = field(default_factory=list)

    @property
    def top_score(self) -> float:
        """Top-1 置信度。"""
        return self.results[0].score if self.results else 0.0


class HybridRetriever:
    """校园知识库混合检索器。"""

    def __init__(
        self,
        knowledge: KnowledgeBase,
        settings: Settings,
        *,
        rewriter: QueryRewriter | None = None,
    ) -> None:
        self._settings = settings
        self._knowledge = knowledge
        self._rewriter = rewriter or QueryRewriter()
        self._vector = TfidfVectorIndex(knowledge.chunks)
        self._keyword = BM25Index(knowledge.chunks)
        self._chunk_by_id = {chunk.chunk_id: chunk for chunk in knowledge.chunks}

    @property
    def rewriter(self) -> QueryRewriter:
        """查询改写器。"""
        return self._rewriter

    def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        category_filter: str | None = None,
        rewritten_queries: list[str] | None = None,
    ) -> RetrievalBundle:
        """执行一次混合检索。

        Args:
            query: 原始查询（可为多条改写查询拼接后的结果）。
            top_k: 返回条数，默认取配置值。
            category_filter: 类别过滤（规章/教务/学工/图书馆）。
            rewritten_queries: 附加的改写查询，用于召回融合。

        Returns:
            含候选、分数与耗时的 :class:`RetrievalBundle`。
        """
        started = time.perf_counter()
        normalized = self._rewriter.normalize(query)
        tokens = tokenize(normalized)
        result_map: dict[str, RetrievalResult] = {}
        vector_rank: dict[str, int] = {}
        keyword_rank: dict[str, int] = {}

        def _collect(text: str, weight: float = 1.0) -> None:
            """把单条查询的向量与关键词召回写入候选池。"""
            nonlocal tokens
            query_tokens = tokenize(text)
            vector_hits = self._vector.search_tokens(
                query_tokens,
                top_k=self._settings.vector_top_k,
                category_filter=category_filter,
            )
            keyword_hits = self._keyword.search_tokens(
                query_tokens,
                top_k=self._settings.keyword_top_k,
                category_filter=category_filter,
            )
            for rank, hit in enumerate(vector_hits):
                target = result_map.setdefault(hit.chunk_id, hit.model_copy())
                target.vector_score = max(target.vector_score, hit.vector_score * weight)
                previous = vector_rank.get(hit.chunk_id)
                if previous is None or rank < previous:
                    vector_rank[hit.chunk_id] = rank
            for rank, hit in enumerate(keyword_hits):
                target = result_map.setdefault(hit.chunk_id, hit.model_copy())
                target.keyword_score = max(target.keyword_score, hit.keyword_score * weight)
                previous = keyword_rank.get(hit.chunk_id)
                if previous is None or rank < previous:
                    keyword_rank[hit.chunk_id] = rank

        _collect(normalized)
        for rewritten in rewritten_queries or []:
            _collect(rewritten, weight=0.6)

        if not result_map:
            return RetrievalBundle(
                query=query,
                normalized_query=normalized,
                latency_ms=int((time.perf_counter() - started) * 1000),
                rewritten_queries=list(rewritten_queries or []),
            )

        # 覆盖率使用原始问题（归一化后）的关键词，避免改写词稀释主信号
        base_tokens = tokenize(normalized)
        k = self._settings.rrf_k
        scored: list[RetrievalResult] = []
        for chunk_id, result in result_map.items():
            fusion = 0.0
            if chunk_id in vector_rank:
                fusion += 1.0 / (k + vector_rank[chunk_id] + 1)
            if chunk_id in keyword_rank:
                fusion += 1.0 / (k + keyword_rank[chunk_id] + 1)

            coverage = self._vector.coverage(base_tokens, chunk_id)
            vector_norm = min(1.0, result.vector_score / 0.45)
            keyword_norm = min(1.0, result.keyword_score / 10.0)
            confidence = 0.55 * coverage + 0.30 * vector_norm + 0.15 * keyword_norm

            result.coverage = round(coverage, 4)
            result.fusion_score = round(fusion, 6)
            result.score = round(min(1.0, confidence), 4)
            scored.append(result)

        scored.sort(key=lambda item: (item.score, item.fusion_score), reverse=True)
        limit = top_k or self._settings.final_top_k
        # 相对分数截断：只保留与 Top-1 同量级的候选，丢掉明显跑题的
        # hard negative / 低分陪跑块。阈值 0.55 在 300 silver 上 Recall@5
        # 保持 1.0，同时把 hard-negative FPR 从 13.3% 降到约 3.9%。
        if scored:
            floor = scored[0].score * 0.55
            relevant = [item for item in scored if item.score >= floor]
            scored = relevant or scored[:1]
        return RetrievalBundle(
            query=query,
            normalized_query=normalized,
            results=scored[:limit],
            vector_candidates=len(vector_rank),
            keyword_candidates=len(keyword_rank),
            latency_ms=int((time.perf_counter() - started) * 1000),
            rewritten_queries=list(rewritten_queries or []),
        )

    def search_for_qa(self, query: str, *, context: list[str] | None = None) -> tuple[RetrievalBundle, list[str]]:
        """问答 Agent 专用：低置信度时自动改写并二次检索。

        Returns:
            ``(最终检索结果, 实际使用的改写查询列表)``。
        """
        bundle = self.search(query)
        if bundle.top_score >= self._settings.low_confidence:
            return bundle, []

        rewrite = self._rewriter.rewrite(query, context=context)
        if not rewrite.rewritten:
            return bundle, []
        merged = self.search(query, rewritten_queries=rewrite.rewritten)
        return merged, rewrite.rewritten

    def search_with_metadata(
        self,
        query: str,
        *,
        top_k: int = 10,
        category_filter: str | None = None,
    ) -> RetrievalBundle:
        """检索调试接口使用，返回更多候选。"""
        return self.search(query, top_k=top_k, category_filter=category_filter)
