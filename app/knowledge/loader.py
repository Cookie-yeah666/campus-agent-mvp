"""知识库加载器。

把 :mod:`app.knowledge.builtin_data` 中的字典数据转换为
:class:`KnowledgeDocument`，并在加载时完成分块与缓存。
"""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.knowledge.builtin_data import DEPARTMENT_CONTACTS, DOCUMENTS
from app.models.domain import KnowledgeChunk, KnowledgeDocument, KnowledgeSection
from app.retrieval.chunking import chunk_document


class KnowledgeBase:
    """内存知识库：文档、分块与分类统计。"""

    def __init__(self, settings: Settings, raw_documents: list[dict[str, Any]] | None = None) -> None:
        self._settings = settings
        self._documents: list[KnowledgeDocument] = []
        self._chunks: list[KnowledgeChunk] = []
        self._documents_by_id: dict[str, KnowledgeDocument] = {}
        self._chunks_by_id: dict[str, KnowledgeChunk] = {}
        self._load(raw_documents or DOCUMENTS)

    def _load(self, raw_documents: list[dict[str, Any]]) -> None:
        """解析原始数据并预计算分块。"""
        for raw in raw_documents:
            document = KnowledgeDocument(
                id=raw["id"],
                title=raw["title"],
                category=raw["category"],
                doc_number=raw.get("doc_number"),
                department=raw.get("department", ""),
                published_at=raw.get("published_at", ""),
                summary=raw.get("summary", ""),
                tags=list(raw.get("tags", [])),
                sections=[
                    KnowledgeSection(
                        heading=section["heading"],
                        paragraphs=list(section["paragraphs"]),
                    )
                    for section in raw.get("sections", [])
                ],
            )
            self._documents.append(document)
            self._documents_by_id[document.id] = document
            for chunk in chunk_document(
                document,
                min_chars=self._settings.chunk_min_chars,
                max_chars=self._settings.chunk_max_chars,
                overlap=self._settings.chunk_overlap_chars,
            ):
                if chunk.chunk_id in self._chunks_by_id:
                    raise ValueError(f"分块 ID 重复: {chunk.chunk_id}")
                self._chunks.append(chunk)
                self._chunks_by_id[chunk.chunk_id] = chunk

    @property
    def documents(self) -> list[KnowledgeDocument]:
        """全部文档（只读视图）。"""
        return list(self._documents)

    @property
    def chunks(self) -> list[KnowledgeChunk]:
        """全部分块（只读视图）。"""
        return list(self._chunks)

    def get_document(self, doc_id: str) -> KnowledgeDocument | None:
        """按 ID 获取文档。"""
        return self._documents_by_id.get(doc_id)

    def get_chunk(self, chunk_id: str) -> KnowledgeChunk | None:
        """按 ID 获取分块。"""
        return self._chunks_by_id.get(chunk_id)

    def chunk_count_for(self, doc_id: str) -> int:
        """统计某文档的分块数。"""
        return sum(1 for chunk in self._chunks if chunk.doc_id == doc_id)

    def categories(self) -> dict[str, int]:
        """按类别统计文档数。"""
        result: dict[str, int] = {}
        for document in self._documents:
            result[document.category] = result.get(document.category, 0) + 1
        return result

    def contacts_for_category(self, category: str | None) -> dict[str, str]:
        """返回某类问题的建议咨询部门。"""
        if category and category in DEPARTMENT_CONTACTS:
            return dict(DEPARTMENT_CONTACTS[category])
        return {"department": "学生服务大厅", "phone": "0512-6716-0000"}

    def stats(self) -> dict[str, int]:
        """知识库规模统计。"""
        return {
            "documents": len(self._documents),
            "chunks": len(self._chunks),
            "characters": sum(document.char_count for document in self._documents),
        }
