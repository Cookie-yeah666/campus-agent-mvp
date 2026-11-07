"""办事流程 Agent。

驱动工作流引擎，负责：
- 判断新任务还是续办；
- 创建/恢复工单；
- 把工作流结果转换为 Agent 回复；
- 同步会话中的当前工单与变量。
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentReply, BaseAgent
from app.agents.router import CARD_REQUEST_RE, RouterResult
from app.config import Settings
from app.core.enums import AuditEventType, IntentType, WorkOrderStatus
from app.core.exceptions import WorkOrderNotFoundError
from app.models.schema import ChatMessage, ChatSession, ToolCallRecord
from app.workflow.engine import TERMINAL_STATUSES, WorkflowEngine

ACTIVE_STATUSES = {
    WorkOrderStatus.AWAITING_INPUT,
    WorkOrderStatus.AWAITING_CONFIRM,
    WorkOrderStatus.AWAITING_APPROVAL,
    WorkOrderStatus.IN_PROGRESS,
    WorkOrderStatus.DRAFT,
}


class WorkflowAgent(BaseAgent):
    """校园卡补办流程 Agent。"""

    name = "workflow-agent"

    def __init__(
        self,
        engine: WorkflowEngine,
        session_manager: Any,
        audit: Any,
        settings: Settings,
        logger: Any,
    ) -> None:
        self._engine = engine
        self._sessions = session_manager
        self._audit = audit
        self._settings = settings
        self._logger = logger

    async def handle(
        self,
        session: ChatSession,
        text: str,
        *,
        history: list[ChatMessage] | None = None,
        router_result: Any = None,
        confirmed: bool | None = None,
    ) -> AgentReply:
        """创建或推进工单。"""
        del history
        active = self._active_workorder(session)

        if active is None:
            is_network = self._is_network_request(text)
            is_leave = self._is_leave_request(text)
            is_card = self._is_card_request(text)
            if isinstance(router_result, RouterResult) and not (is_card or is_network or is_leave):
                self._audit.record(
                    AuditEventType.HANDOFF.value,
                    session.id,
                    None,
                    {"reason": "unsupported_workflow", "input": text},
                )
                return AgentReply(
                    content=(
                        "目前可线上办理的是**校园卡补办**、**网络报修**和**请假申请**"
                        "（在读证明等尚未接入线上办理）。\n\n"
                        "我可以帮你查制度，或转人工登记需求。"
                    ),
                    confidence=0.5,
                    metadata={"handoff": True, "reason": "unsupported_workflow"},
                    suggested_actions=["我要补办校园卡", "我要报修网络", "转人工咨询"],
                    trace=[],
                )
            workflow_type = (
                "network_repair"
                if is_network
                else "leave_request"
                if is_leave
                else "card_reissue"
            )
            result = await self._engine.start(workflow_type, session.id, text)
        else:
            result = await self._engine.resume(active.id, text, confirmed=confirmed)

        workorder = result.workorder
        tool_calls = self._tool_calls_from_trace(result.trace)

        if workorder.status in ACTIVE_STATUSES:
            self._sessions.set_workflow(session, workorder.id)
        else:
            self._sessions.set_workflow(session, None)

        session.variables.update(
            {
                key: value
                for key, value in workorder.user_inputs.items()
                if isinstance(value, (str, int, float, bool))
            }
        )
        campus = workorder.user_inputs.get("campus")
        if campus and session.title.strip() in {
            self._sessions.DEFAULT_TITLE,
            "我要补办校园卡",
            "我要补办校园卡。",
            "我要报修网络",
            "我要报修网络。",
        }:
            if workorder.workflow_type == "network_repair":
                session.title = f"网络报修 · {campus}"
            elif workorder.workflow_type == "leave_request":
                session.title = f"请假申请 · {campus}"
            else:
                session.title = f"校园卡补办 · {campus}"
        session.variables["last_workorder_id"] = workorder.id
        if workorder.receipt_number:
            session.variables["last_receipt"] = workorder.receipt_number
        self._sessions.save(session)

        metadata = {
            "intent": IntentType.WORKFLOW.value,
            "workflow_type": workorder.workflow_type,
            "workorder_id": workorder.id,
            "workorder_status": workorder.status.value,
            "duplicate": result.duplicate,
            "receipt_number": workorder.receipt_number,
        }
        return AgentReply(
            content=result.message,
            confidence=0.96,
            metadata=metadata,
            requires_confirmation=result.requires_confirmation,
            workorder=workorder,
            suggested_actions=result.suggested_actions,
            trace=result.trace,
            tool_calls=tool_calls,
        )

    def _active_workorder(self, session: ChatSession) -> Any | None:
        """获取会话中仍在进行的工单。"""
        workorder_id = session.current_workflow_id
        if not workorder_id:
            return None
        try:
            workorder = self._engine.store.get(workorder_id)
        except WorkOrderNotFoundError:
            session.current_workflow_id = None
            return None
        if workorder.status in TERMINAL_STATUSES:
            session.current_workflow_id = None
            return None
        return workorder

    @staticmethod
    def _is_card_request(text: str) -> bool:
        """判断是否为校园卡补办请求。"""
        return bool(CARD_REQUEST_RE.search(text)) or "补卡" in text or "补办" in text

    @staticmethod
    def _is_leave_request(text: str) -> bool:
        """判断是否为请假申请。"""
        return any(word in text for word in ("我要请假", "申请请假", "请假申请", "办理请假", "请个假"))

    @staticmethod
    def _is_network_request(text: str) -> bool:
        """判断是否为网络报修请求。"""
        return any(
            word in text
            for word in ("报修网络", "网络报修", "报修", "断网", "没网", "WiFi", "wifi", "网线", "路由器")
        )

    @staticmethod
    def _tool_calls_from_trace(trace: list[Any]) -> list[ToolCallRecord]:
        """从轨迹中还原工具调用记录。"""
        records: list[ToolCallRecord] = []
        for step in trace:
            if getattr(step, "type", "") != "tool":
                continue
            data = getattr(step, "data", {}) or {}
            records.append(
                ToolCallRecord(
                    tool_name=str(data.get("tool", "")),
                    arguments=dict(data.get("arguments", {}) or {}),
                    success=getattr(step, "status", "") == "success",
                    latency_ms=getattr(step, "latency_ms", 0) or 0,
                    error=None if getattr(step, "status", "") == "success" else step.detail,
                )
            )
        return records
