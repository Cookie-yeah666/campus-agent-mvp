"""系统枚举定义。

枚举的字符串值会直接出现在 API 响应与前端界面中，因此统一使用
小写英文值；展示用中文文案由前端或提示词模板负责。
"""

from __future__ import annotations

from enum import Enum


class IntentType(str, Enum):
    """用户意图类型。"""

    QA = "qa"
    WORKFLOW = "workflow"
    HUMAN_HANDOFF = "human_handoff"
    CLARIFY = "clarify"


class MessageRole(str, Enum):
    """对话消息角色。"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class WorkOrderStatus(str, Enum):
    """工单状态。"""

    DRAFT = "draft"
    AWAITING_INPUT = "awaiting_input"
    AWAITING_CONFIRM = "awaiting_confirm"
    AWAITING_APPROVAL = "awaiting_approval"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TRANSFERRED_HUMAN = "transferred_human"


class NodeType(str, Enum):
    """工作流节点类型。"""

    START = "start"
    INTENT = "intent"
    PARAMETER_EXTRACT = "parameter_extract"
    CONDITION = "condition"
    TOOL_CALL = "tool_call"
    CONFIRMATION = "confirmation"
    APPROVAL = "approval"
    RESULT = "result"
    HUMAN_HANDOFF = "human_handoff"
    END = "end"


class NodeOutcome(str, Enum):
    """节点执行结果类型。"""

    CONTINUE = "continue"
    PAUSE = "pause"
    FINISH = "finish"
    FAIL = "fail"
    HANDOFF = "handoff"


class NodeStatus(str, Enum):
    """节点执行记录状态。"""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class KnowledgeCategory(str, Enum):
    """知识库文档类别。"""

    REGULATION = "规章"
    ACADEMIC = "教务"
    STUDENT_AFFAIRS = "学工"
    LIBRARY = "图书馆"


class AuditEventType(str, Enum):
    """审计事件类型。"""

    MESSAGE = "message"
    AUTH = "auth"
    INTENT = "intent"
    RETRIEVAL = "retrieval"
    TOOL_CALL = "tool_call"
    NODE_TRANSITION = "node_transition"
    CONFIRMATION = "confirmation"
    IDEMPOTENCY = "idempotency"
    HANDOFF = "handoff"
    ERROR = "error"
    EVALUATION = "evaluation"


class TraceType(str, Enum):
    """前端轨迹面板的步骤类型。"""

    INTENT = "intent"
    RETRIEVAL = "retrieval"
    REWRITE = "rewrite"
    GENERATION = "generation"
    VALIDATION = "validation"
    TOOL = "tool"
    NODE = "node"
    CONFIRMATION = "confirmation"
    HANDOFF = "handoff"
    IDEMPOTENCY = "idempotency"


class TraceStatus(str, Enum):
    """轨迹步骤状态。"""

    SUCCESS = "success"
    WARNING = "warning"
    FAILED = "failed"
    RUNNING = "running"
