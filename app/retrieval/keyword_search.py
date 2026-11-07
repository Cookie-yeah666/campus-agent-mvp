"""简化版 BM25 关键词检索。

实现词频、逆文档频率与长度归一化，并对标题、章节名和文号
中的精确命中给予额外加权。
"""

from __future__ import annotations

import math
from collections import Counter

from app.models.domain import KnowledgeChunk, RetrievalResult
from app.retrieval.tokenizer import tokenize


class BM25Index:
    """BM25 关键词索引。"""

    def __init__(
        self,
        chunks: list[KnowledgeChunk],
        *,
        k1: float = 1.5,
        b: float = 0.75,
        title_boost: float = 1.2,
        doc_number_boost: float = 1.5,
    ) -> None:
        if not chunks:
            raise ValueError("关键词索引至少需要一个分块")
        self._chunks = list(chunks)
        self._k1 = k1
        self._b = b
        self._title_boost = title_boost
        self._doc_number_boost = doc_number_boost
        self._token_counts: dict[str, Counter[str]] = {}
        self._lengths: dict[str, int] = {}
        self._title_tokens: dict[str, set[str]] = {}
        self._number_tokens: dict[str, set[str]] = {}
        self._idf: dict[str, float] = {}
        self._avg_length = 0.0
        self._fit()

    def _fit(self) -> None:
        """统计词频、文档频率与平均文档长度。"""
        document_frequency: Counter[str] = Counter()
        total_length = 0
        for chunk in self._chunks:
            tokens = tokenize(f"{chunk.chapter} {chunk.content}")
            counts = Counter(tokens)
            self._token_counts[chunk.chunk_id] = counts
            self._lengths[chunk.chunk_id] = len(tokens)
            total_length += len(tokens)
            self._title_tokens[chunk.chunk_id] = set(tokenize(chunk.doc_title))
            self._number_tokens[chunk.chunk_id] = set(
                tokenize(chunk.doc_number or "", remove_stopwords=False)
            )
            document_frequency.update(set(tokens))

        total = len(self._chunks)
        self._avg_length = total_length / total if total else 1.0
        self._idf = {
            token: math.log(1 + (total - frequency + 0.5) / (frequency + 0.5))
            for token, frequency in document_frequency.items()
        }

    def _score(self, tokens: list[str], chunk: KnowledgeChunk) -> float:
        """计算单个分块的 BM25 得分。"""
        counts = self._token_counts[chunk.chunk_id]
        length = self._lengths[chunk.chunk_id] or 1
        score = 0.0
        for token in set(tokens):
            frequency = counts.get(token, 0)
            if frequency <= 0:
                continue
            idf = self._idf.get(token, 0.0)
            denominator = frequency + self._k1 * (
                1 - self._b + self._b * length / self._avg_length
            )
            score += idf * frequency * (self._k1 + 1) / denominator
            if token in self._title_tokens[chunk.chunk_id]:
                score += idf * self._title_boost
            if token in self._number_tokens[chunk.chunk_id]:
                score += idf * self._doc_number_boost
        return score

    def search_tokens(
        self,
        tokens: list[str],
        top_k: int,
        category_filter: str | None = None,
    ) -> list[RetrievalResult]:
        """按查询词检索。"""
        if not tokens:
            return []
        scored: list[tuple[float, KnowledgeChunk]] = []
        for chunk in self._chunks:
            if category_filter and chunk.category != category_filter:
                continue
            score = self._score(tokens, chunk)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievalResult(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                doc_title=chunk.doc_title,
                chapter=chunk.chapter,
                doc_number=chunk.doc_number,
                category=chunk.category,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                keyword_score=round(score, 6),
                score=round(score, 6),
            )
            for score, chunk in scored[:top_k]
        ]

    def search(
        self,
        query: str,
        top_k: int = 10,
        category_filter: str | None = None,
    ) -> list[RetrievalResult]:
        """按原始查询检索。"""
        return self.search_tokens(tokenize(query), top_k=top_k, category_filter=category_filter)
