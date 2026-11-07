"""API 契约模型。

这些模型同时用于请求校验、响应序列化和 JSON 落盘，
字段命名与需求文档保持一致，额外字段只增不改。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.enums import MessageRole, TraceStatus, WorkOrderStatus


def utc_now() -> datetime:
    """返回带时区的当前时间（UTC）。"""
    return datetime.now(timezone.utc)


class Citation(BaseModel):
    """回答中的引用来源。"""

    doc_id: str
    doc_title: str
    chapter: str
    doc_number: str | None = None
    chunk_id: str
    content_snippet: str
    score: float = 0.0
    category: str | None = None


class ToolCallRecord(BaseModel):
    """一次工具调用的留痕记录。"""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    success: bool
    latency_ms: int = 0
    error: str | None = None
    result_summary: str | None = None


class TraceStep(BaseModel):
    """Agent 执行轨迹的单个步骤，用于前端右侧轨迹面板与回放。"""

    type: str
    title: str
    detail: str | None = None
    status: str = TraceStatus.SUCCESS.value
    latency_ms: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """会话中的一条消息。"""

    id: str
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=utc_now)
    citations: list[Citation] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace: list[TraceStep] = Field(default_factory=list)


class ChatSession(BaseModel):
    """多轮会话。"""

    id: str
    title: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    messages: list[ChatMessage] = Field(default_factory=list)
    current_workflow_id: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    owner_id: str | None = None
    owner_role: str | None = None
    owner_college: str | None = None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        """标题为空时回退到默认值，避免侧边栏出现空白项。"""
        value = value.strip()
        return value or "新的对话"


class NodeExecutionRecord(BaseModel):
    """工作流节点执行记录。"""

    node_id: str
    node_name: str
    node_type: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=utc_now)
    duration_ms: int = 0
    status: str = "success"
    error: str | None = None


class WorkOrder(BaseModel):
    """办事工单。"""

    id: str
    receipt_number: str = ""
    workflow_type: str
    definition_version: str = ""
    definition_snapshot: dict[str, Any] | None = None
    status: WorkOrderStatus = WorkOrderStatus.DRAFT
    idempotency_key: str = ""
    user_inputs: dict[str, Any] = Field(default_factory=dict)
    current_node: str = ""
    node_history: list[NodeExecutionRecord] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    error_message: str | None = None
    session_id: str | None = None
    duplicate_of: str | None = None
    handoff_reason: str | None = None
    handoff_at: datetime | None = None
    approval_role: str | None = None
    assignee_id: str | None = None
    resolved_at: datetime | None = None


class AuditLog(BaseModel):
    """审计日志条目。"""

    id: str
    session_id: str
    workorder_id: str | None = None
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str = ""
    hash: str = ""
    timestamp: datetime = Field(default_factory=utc_now)


class ChatRequest(BaseModel):
    """发送消息请求。"""

    session_id: str | None = None
    message: str = Field(min_length=1, max_length=2000)
    idempotency_key: str | None = None

    @field_validator("message")
    @classmethod
    def _strip_message(cls, value: str) -> str:
        """去掉首尾空白，空白输入视为非法。"""
        value = value.strip()
        if not value:
            raise ValueError("消息内容不能为空")
        return value


class ChatResponse(BaseModel):
    """发送消息响应。"""

    session_id: str
    message: ChatMessage
    intent: str
    intent_confidence: float
    requires_confirmation: bool = False
    workorder: WorkOrder | None = None
    suggested_actions: list[str] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class ConfirmRequest(BaseModel):
    """确认/取消办事节点。"""

    action: Literal["confirm", "cancel"]
    note: str | None = Field(default=None, max_length=200)


class SessionSummary(BaseModel):
    """会话列表项。"""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    current_workflow_id: str | None = None
    last_message_preview: str = ""


class SessionDetail(ChatSession):
    """会话详情（当前与 ChatSession 字段一致，便于后续扩展）。"""


class SessionListResponse(BaseModel):
    """会话列表响应。"""

    items: list[SessionSummary]
    total: int


class WorkOrderListResponse(BaseModel):
    """工单列表响应。"""

    items: list[WorkOrder]
    total: int
    counts: dict[str, int] = Field(default_factory=dict)


class AuditListResponse(BaseModel):
    """审计日志列表响应。"""

    items: list[AuditLog]
    total: int


class KnowledgeDocumentSummary(BaseModel):
    """知识库文档摘要。"""

    id: str
    title: str
    category: str
    doc_number: str | None = None
    department: str = ""
    published_at: str = ""
    summary: str = ""
    section_count: int = 0
    chunk_count: int = 0
    char_count: int = 0
    tags: list[str] = Field(default_factory=list)


class KnowledgeListResponse(BaseModel):
    """知识库列表响应。"""

    items: list[KnowledgeDocumentSummary]
    total: int
    categories: list[dict[str, Any]] = Field(default_factory=list)


class RetrievalSearchResponse(BaseModel):
    """检索调试响应。"""

    query: str
    normalized_query: str
    rewritten_queries: list[str] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int = 0


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str
    app: str
    version: str
    uptime_seconds: float
    started_at: datetime
    knowledge_documents: int
    knowledge_chunks: int
    sessions: int
    workorders: int
    tools: list[str] = Field(default_factory=list)
    llm_model: str
    environment: str = "local"
    server_time: datetime = Field(default_factory=utc_now)
    data_dir: str = ""


class EvaluationQueryResult(BaseModel):
    """单条评测查询结果。"""

    query: str
    category: str
    expected_doc_id: str
    retrieved_doc_ids: list[str] = Field(default_factory=list)
    hit: bool = False
    rank: int | None = None
    latency_ms: int = 0


class EvaluationReport(BaseModel):
    """检索与问答评测报告。"""

    run_id: str
    created_at: datetime = Field(default_factory=utc_now)
    dataset_size: int
    recall_at_5: float
    mrr_at_5: float
    avg_latency_ms: float
    p95_latency_ms: float
    refusal_rate: float = 0.0
    by_category: dict[str, dict[str, float]] = Field(default_factory=dict)
    details: list[EvaluationQueryResult] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """统一错误响应。"""

    code: str
    message: str
    detail: Any = None
