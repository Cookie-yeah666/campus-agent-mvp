"""TF-IDF 向量检索。

不依赖外部 embedding 模型：用 jieba 分词后的 TF-IDF 稀疏向量
模拟文档向量，以余弦相似度召回候选分块。
"""

from __future__ import annotations

import math
from collections import Counter

from app.models.domain import KnowledgeChunk, RetrievalResult
from app.retrieval.tokenizer import tokenize


class TfidfVectorIndex:
    """基于内存的 TF-IDF 向量索引。"""

    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        if not chunks:
            raise ValueError("向量索引至少需要一个分块")
        self._chunks = list(chunks)
        self._chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        self._idf: dict[str, float] = {}
        self._vectors: dict[str, dict[str, float]] = {}
        self._norms: dict[str, float] = {}
        self._token_sets: dict[str, set[str]] = {}
        self._fit()

    def _fit(self) -> None:
        """拟合词表、IDF 与文档向量。"""
        document_frequency: Counter[str] = Counter()
        tokenized: dict[str, list[str]] = {}
        for chunk in self._chunks:
            tokens = tokenize(f"{chunk.doc_title} {chunk.chapter} {chunk.content}")
            tokenized[chunk.chunk_id] = tokens
            self._token_sets[chunk.chunk_id] = set(tokens)
            document_frequency.update(set(tokens))

        total = len(self._chunks)
        self._idf = {
            token: math.log((total + 1) / (frequency + 1)) + 1.0
            for token, frequency in document_frequency.items()
        }

        for chunk in self._chunks:
            counts = Counter(tokenized[chunk.chunk_id])
            vector: dict[str, float] = {}
            for token, count in counts.items():
                weight = (1.0 + math.log(count)) * self._idf.get(token, 1.0)
                vector[token] = weight
            norm = math.sqrt(sum(weight * weight for weight in vector.values())) or 1.0
            self._vectors[chunk.chunk_id] = {token: weight / norm for token, weight in vector.items()}
            self._norms[chunk.chunk_id] = norm

    @property
    def chunks(self) -> list[KnowledgeChunk]:
        """索引中的全部分块。"""
        return list(self._chunks)

    @property
    def idf(self) -> dict[str, float]:
        """词 -> IDF 权重。"""
        return dict(self._idf)

    def _query_vector(self, tokens: list[str]) -> dict[str, float]:
        """把查询词转换为与文档同空间的归一化向量。"""
        counts = Counter(token for token in tokens if token in self._idf)
        vector = {
            token: (1.0 + math.log(count)) * self._idf[token]
            for token, count in counts.items()
        }
        norm = math.sqrt(sum(weight * weight for weight in vector.values())) or 1.0
        return {token: weight / norm for token, weight in vector.items()}

    def search_tokens(
        self,
        tokens: list[str],
        top_k: int,
        category_filter: str | None = None,
    ) -> list[RetrievalResult]:
        """按查询词检索。"""
        query_vector = self._query_vector(tokens)
        if not query_vector:
            return []
        scored: list[tuple[float, KnowledgeChunk]] = []
        for chunk in self._chunks:
            if category_filter and chunk.category != category_filter:
                continue
            vector = self._vectors[chunk.chunk_id]
            score = sum(weight * vector.get(token, 0.0) for token, weight in query_vector.items())
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
                vector_score=round(score, 6),
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
        """按原始查询检索（接口与关键词检索保持一致）。"""
        return self.search_tokens(tokenize(query), top_k=top_k, category_filter=category_filter)

    def coverage(self, tokens: list[str], chunk_id: str) -> float:
        """计算查询词在分块中的 IDF 加权覆盖率（0~1）。

        覆盖率比余弦相似度更直观地反映“问题里的关键概念有多少被这一段覆盖”，
        用作置信度判断的主信号。
        """
        query_terms = set(tokens)
        if not query_terms:
            return 0.0
        # 语料中不存在的词（如“火锅”）同样要计入分母，并按最高 IDF 惩罚，
        # 否则越界问题会因为“所有已知词都命中”而得到虚高的覆盖率。
        default_idf = max(self._idf.values(), default=1.0)
        total_weight = sum(self._idf.get(token, default_idf) for token in query_terms)
        if total_weight <= 0:
            return 0.0
        chunk_terms = self._token_sets.get(chunk_id, set())
        hit_weight = sum(
            self._idf.get(token, default_idf) for token in query_terms if token in chunk_terms
        )
        return hit_weight / total_weight
