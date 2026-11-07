"""领域模型。

与 :mod:`app.models.schema` 的 API 契约不同，这里的模型描述
知识库、检索结果、工具与工作流定义等内部结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import NodeOutcome, NodeType
from app.models.schema import ToolCallRecord, TraceStep, WorkOrder


class KnowledgeSection(BaseModel):
    """文档中的一个章节。"""

    heading: str
    paragraphs: list[str] = Field(default_factory=list)


class KnowledgeDocument(BaseModel):
    """知识库文档。"""

    id: str
    title: str
    category: str
    doc_number: str | None = None
    department: str = ""
    published_at: str = ""
    summary: str = ""
    sections: list[KnowledgeSection] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        """拼接标题与正文，供分块与统计使用。"""
        parts = [self.title]
        for section in self.sections:
            parts.append(section.heading)
            parts.extend(section.paragraphs)
        return "\n".join(parts)

    @property
    def char_count(self) -> int:
        """文档总字数。"""
        return len(self.full_text)


class KnowledgeChunk(BaseModel):
    """文档分块，是检索的最小单位。"""

    chunk_id: str
    doc_id: str
    doc_title: str
    chapter: str
    doc_number: str | None = None
    category: str
    chunk_index: int
    content: str

    @property
    def display_title(self) -> str:
        """引用卡片使用的标题。"""
        return f"《{self.doc_title}》· {self.chapter}"


class RetrievalResult(BaseModel):
    """混合检索结果。"""

    chunk_id: str
    doc_id: str
    doc_title: str
    chapter: str
    doc_number: str | None = None
    category: str
    chunk_index: int
    content: str
    vector_score: float = 0.0
    keyword_score: float = 0.0
    coverage: float = 0.0
    fusion_score: float = 0.0
    score: float = 0.0


class ToolResult(BaseModel):
    """工具统一返回结构。"""

    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    latency_ms: int = 0
    timed_out: bool = False

    @classmethod
    def ok(cls, data: dict[str, Any], latency_ms: int = 0) -> "ToolResult":
        """构造成功结果。"""
        return cls(success=True, data=data, latency_ms=latency_ms)

    @classmethod
    def fail(
        cls,
        error_message: str,
        *,
        latency_ms: int = 0,
        timed_out: bool = False,
    ) -> "ToolResult":
        """构造失败结果。"""
        return cls(
            success=False,
            error_message=error_message,
            latency_ms=latency_ms,
            timed_out=timed_out,
        )


class ToolDefinition(BaseModel):
    """工具元数据，供 Agent 与前端展示。"""

    name: str
    description: str
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 5
    category: str = "校园业务"


class WorkflowNodeDef(BaseModel):
    """工作流节点声明。"""

    id: str
    name: str
    node_type: NodeType
    description: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    """工作流边。

    ``condition`` 为空表示默认边；否则为 :mod:`app.workflow.conditions`
    中注册的条件函数名。
    """

    source: str
    target: str
    condition: str | None = None
    label: str = ""


class WorkflowDefinition(BaseModel):
    """声明式工作流定义：节点列表 + 边列表。"""

    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    start_node: str
    nodes: list[WorkflowNodeDef] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)

    def get_node(self, node_id: str) -> WorkflowNodeDef | None:
        """按 ID 查找节点。"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def outgoing_edges(self, node_id: str) -> list[WorkflowEdge]:
        """返回节点的全部出边（保持声明顺序）。"""
        return [edge for edge in self.edges if edge.source == node_id]


class NodeResult(BaseModel):
    """节点执行结果。"""

    outcome: NodeOutcome
    next_node: str | None = None
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    suggested_actions: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    error: str | None = None

    @classmethod
    def go(cls, next_node: str, data: dict[str, Any] | None = None) -> "NodeResult":
        """继续执行下一节点。"""
        return cls(outcome=NodeOutcome.CONTINUE, next_node=next_node, data=data or {})

    @classmethod
    def pause(
        cls,
        message: str,
        *,
        suggested_actions: list[str] | None = None,
        requires_confirmation: bool = False,
        data: dict[str, Any] | None = None,
    ) -> "NodeResult":
        """暂停，等待用户输入或确认。"""
        return cls(
            outcome=NodeOutcome.PAUSE,
            message=message,
            suggested_actions=suggested_actions or [],
            requires_confirmation=requires_confirmation,
            data=data or {},
        )

    @classmethod
    def finish(
        cls,
        message: str,
        *,
        data: dict[str, Any] | None = None,
        suggested_actions: list[str] | None = None,
    ) -> "NodeResult":
        """流程正常结束。"""
        return cls(
            outcome=NodeOutcome.FINISH,
            message=message,
            data=data or {},
            suggested_actions=suggested_actions or [],
        )

    @classmethod
    def handoff(cls, message: str, *, error: str | None = None) -> "NodeResult":
        """转人工。"""
        return cls(outcome=NodeOutcome.HANDOFF, message=message, error=error)

    @classmethod
    def fail(cls, message: str, *, error: str | None = None) -> "NodeResult":
        """执行失败。"""
        return cls(outcome=NodeOutcome.FAIL, message=message, error=error)


@dataclass
class WorkflowContext:
    """一次工作流执行的运行时上下文。"""

    workorder: WorkOrder
    session_id: str
    user_input: str
    variables: dict[str, Any]
    settings: Any
    tool_registry: Any
    audit: Any
    idempotency: Any
    logger: Any
    workorder_store: Any = None
    definition: WorkflowDefinition | None = None
    confirmed: bool | None = None
    tool_records: list[ToolCallRecord] = field(default_factory=list)
    trace: list[TraceStep] = field(default_factory=list)

    def set_variable(self, key: str, value: Any) -> None:
        """写入工作流变量（同时同步到工单输入，便于审计）。"""
        self.variables[key] = value
        self.workorder.user_inputs[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """读取工作流变量。"""
        return self.variables.get(key, default)

    def add_trace(
        self,
        step_type: str,
        title: str,
        *,
        detail: str | None = None,
        status: str = "success",
        latency_ms: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """追加一条前端轨迹记录。"""
        self.trace.append(
            TraceStep(
                type=step_type,
                title=title,
                detail=detail,
                status=status,
                latency_ms=latency_ms,
                data=data or {},
            )
        )


class WorkflowState(BaseModel):
    """工单的当前状态快照。"""

    workorder_id: str
    workflow_type: str
    status: str
    current_node: str
    variables: dict[str, Any] = Field(default_factory=dict)
    node_history: list[Any] = Field(default_factory=list)


class WorkflowRunResult(BaseModel):
    """工作流推进后返回给 Agent 的结果。"""

    workorder: WorkOrder
    message: str
    requires_confirmation: bool = False
    suggested_actions: list[str] = Field(default_factory=list)
    finished: bool = False
    duplicate: bool = False
    trace: list[TraceStep] = Field(default_factory=list)
