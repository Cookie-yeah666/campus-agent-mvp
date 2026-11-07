"""Agent 基类与统一返回结构。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.models.domain import RetrievalResult
from app.models.schema import (
    ChatMessage,
    ChatSession,
    Citation,
    ToolCallRecord,
    TraceStep,
    WorkOrder,
)


class AgentReply(BaseModel):
    """Agent 处理结果。"""

    content: str
    citations: list[Citation] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    workorder: WorkOrder | None = None
    suggested_actions: list[str] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)


class BaseAgent(ABC):
    """Agent 抽象基类。"""

    name: str = "base-agent"

    @abstractmethod
    async def handle(
        self,
        session: ChatSession,
        text: str,
        *,
        history: list[ChatMessage] | None = None,
        router_result: Any = None,
        confirmed: bool | None = None,
    ) -> AgentReply:
        """处理一轮用户输入。"""
        raise NotImplementedError


def citation_from_result(result: RetrievalResult, *, snippet_limit: int = 120) -> Citation:
    """把检索结果转换为引用卡片。"""
    content = result.content.strip()
    snippet = content if len(content) <= snippet_limit else content[:snippet_limit] + "…"
    return Citation(
        doc_id=result.doc_id,
        doc_title=result.doc_title,
        chapter=result.chapter,
        doc_number=result.doc_number,
        chunk_id=result.chunk_id,
        content_snippet=snippet,
        score=result.score,
        category=result.category,
    )
