"""领域异常。

API 层统一把 :class:`CampusAgentError` 转换为
``{"code": ..., "message": ..., "detail": ...}`` 结构的错误响应。
"""

from __future__ import annotations

from typing import Any


class CampusAgentError(Exception):
    """所有业务异常的基类。"""

    code: str = "campus_agent_error"
    status_code: int = 500
    message: str = "服务内部错误"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        detail: Any = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.detail = detail
        super().__init__(self.message)


class SessionNotFoundError(CampusAgentError):
    """会话不存在。"""

    code = "session_not_found"
    status_code = 404
    message = "会话不存在或已被删除"


class WorkOrderNotFoundError(CampusAgentError):
    """工单不存在。"""

    code = "workorder_not_found"
    status_code = 404
    message = "工单不存在"


class KnowledgeNotFoundError(CampusAgentError):
    """知识库文档不存在。"""

    code = "knowledge_not_found"
    status_code = 404
    message = "知识库文档不存在"


class KnowledgeInsufficientError(CampusAgentError):
    """知识库无法支撑回答。"""

    code = "knowledge_insufficient"
    status_code = 200
    message = "知识库中没有可靠依据"


class ToolExecutionError(CampusAgentError):
    """工具执行失败。"""

    code = "tool_execution_failed"
    status_code = 502
    message = "业务系统调用失败"


class ToolTimeoutError(ToolExecutionError):
    """工具调用超时。"""

    code = "tool_timeout"
    status_code = 504
    message = "业务系统响应超时"


class ParameterValidationError(CampusAgentError):
    """参数校验失败。"""

    code = "parameter_invalid"
    status_code = 422
    message = "参数格式不正确"


class WorkflowStateError(CampusAgentError):
    """工作流状态非法。"""

    code = "workflow_state_invalid"
    status_code = 409
    message = "当前工单状态不允许该操作"


class IdempotencyConflictError(CampusAgentError):
    """幂等键冲突（正常情况下应返回原工单而非抛错）。"""

    code = "idempotency_conflict"
    status_code = 409
    message = "检测到重复提交"


class EvaluationError(CampusAgentError):
    """评测任务执行失败。"""

    code = "evaluation_failed"
    status_code = 500
    message = "评测任务执行失败"
