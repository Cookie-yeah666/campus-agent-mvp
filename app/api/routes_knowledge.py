"""知识库浏览与检索调试接口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.deps import get_container
from app.models.domain import KnowledgeDocument
from app.models.schema import (
    KnowledgeDocumentSummary,
    KnowledgeListResponse,
    RetrievalSearchResponse,
)

router = APIRouter(tags=["知识库"])


@router.get(
    "/knowledge/documents",
    response_model=KnowledgeListResponse,
    summary="知识库文档列表",
)
def list_documents(category: str | None = Query(default=None)) -> KnowledgeListResponse:
    """按类别返回文档摘要与分块统计。"""
    container = get_container()
    documents = container.knowledge.documents
    if category:
        documents = [document for document in documents if document.category == category]
    items = [
        KnowledgeDocumentSummary(
            id=document.id,
            title=document.title,
            category=document.category,
            doc_number=document.doc_number,
            department=document.department,
            published_at=document.published_at,
            summary=document.summary,
            section_count=len(document.sections),
            chunk_count=container.knowledge.chunk_count_for(document.id),
            char_count=document.char_count,
            tags=document.tags,
        )
        for document in documents
    ]
    categories = [
        {"name": name, "count": count}
        for name, count in container.knowledge.categories().items()
    ]
    return KnowledgeListResponse(
        items=items,
        total=len(items),
        categories=categories,
    )


@router.get(
    "/knowledge/documents/{doc_id}",
    response_model=KnowledgeDocument,
    summary="知识库文档详情",
)
def get_document(doc_id: str) -> KnowledgeDocument:
    """返回文档全文与章节结构。"""
    document = get_container().knowledge.get_document(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "knowledge_not_found"})
    return document


@router.get(
    "/knowledge/search",
    response_model=RetrievalSearchResponse,
    summary="混合检索调试",
)
def search_knowledge(
    q: str = Query(min_length=1, max_length=200),
    category: str | None = Query(default=None),
    top_k: int = Query(default=5, ge=1, le=20),
) -> RetrievalSearchResponse:
    """执行一次混合检索，返回向量分、BM25 分、覆盖率与融合分。"""
    container = get_container()
    bundle = container.retriever.search(q, top_k=top_k, category_filter=category)
    rewrite = container.retriever.rewriter.rewrite(q)
    return RetrievalSearchResponse(
        query=q,
        normalized_query=bundle.normalized_query,
        rewritten_queries=rewrite.rewritten,
        results=[result.model_dump() for result in bundle.results],
        latency_ms=bundle.latency_ms,
    )


@router.get("/knowledge/categories", summary="知识库分类统计")
def knowledge_categories() -> list[dict[str, Any]]:
    """返回四类知识库的文档数、分块数与字数。"""
    container = get_container()
    result: list[dict[str, Any]] = []
    for category, count in container.knowledge.categories().items():
        documents = [doc for doc in container.knowledge.documents if doc.category == category]
        result.append(
            {
                "name": category,
                "documents": count,
                "chunks": sum(
                    container.knowledge.chunk_count_for(doc.id) for doc in documents
                ),
                "characters": sum(doc.char_count for doc in documents),
            }
        )
    return result
