"""对话编排服务。

Web API、CLI 与测试共用本服务：统一处理会话、路由、
Agent 调用、消息落库与审计，避免多入口逻辑分叉。
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.agents.base import AgentReply
from app.agents.qa_agent import QAAgent
from app.agents.router import IntentRouter, RouterResult
from app.agents.workflow_agent import WorkflowAgent
from app.config import Settings
from app.core.enums import AuditEventType, IntentType, MessageRole, WorkOrderStatus
from app.core.exceptions import WorkflowStateError
from app.memory.session import SessionManager
from app.models.schema import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatSession,
    ConfirmRequest,
)
from app.workflow.engine import TERMINAL_STATUSES, WorkflowEngine

HANDOFF_WORDS = ("转人工", "人工客服", "找人工", "人工咨询", "联系人工")
WORKORDER_LOOKUP_WORDS = {"查看工单", "查看工单详情", "查询工单"}

# 同一会话内按话题隔离 QA 上下文。新话题不继承上一话题，短追问才继承。
WORKFLOW_TOPICS = {
    "card_reissue": "校园卡",
    "network_repair": "网络",
    "leave_request": "请假",
}

TOPIC_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("奖学金", ("奖学金", "助学金", "助学贷款", "勤工助学", "资助")),
    ("转专业", ("转专业", "转系")),
    ("校园卡", ("校园卡", "补卡", "补办", "挂失", "工本费")),
    ("图书", ("借阅", "续借", "逾期", "自习室", "座位", "电子资源", "数据库")),
    ("请假", ("请假", "销假", "旷课", "门禁", "晚归")),
    ("教务", ("选课", "学分", "成绩", "补考", "重修", "缓考", "作弊", "处分")),
    ("网络", ("网络", "报修", "断网", "网线", "维修")),
)


def _now() -> datetime:
    """当前 UTC 时间。"""
    return datetime.now(timezone.utc)


class ChatService:
    """对话编排器。"""

    def __init__(
        self,
        router: IntentRouter,
        qa_agent: QAAgent,
        workflow_agent: WorkflowAgent,
        sessions: SessionManager,
        engine: WorkflowEngine,
        audit: Any,
        settings: Settings,
        logger: Any,
    ) -> None:
        self._router = router
        self._qa = qa_agent
        self._workflow = workflow_agent
        self._sessions = sessions
        self._engine = engine
        self._audit = audit
        self._settings = settings
        self._logger = logger

    async def send(
        self,
        request: ChatRequest,
        *,
        owner: Any | None = None,
    ) -> ChatResponse:
        """处理一条用户消息。"""
        session = (
            self._sessions.get(request.session_id)
            if request.session_id
            else self._sessions.create(owner=owner)
        )
        active = self._active_workorder(session)
        active_topic = WORKFLOW_TOPICS.get(getattr(active, "workflow_type", ""))
        message_topic = self._detect_topic(request.message)
        topic_conflict = bool(
            active
            and active_topic
            and message_topic
            and message_topic != active_topic
        )
        # 用户中途问了另一个话题后，原工单先暂停；后续短追问继续 QA，
        # 只有明确回到原话题或说“确认/取消”时才恢复工单。
        if active and session.variables.get("workflow_suspended"):
            explicit_resume = request.message.strip() in {"确认", "确认提交", "取消", "提交"}
            if explicit_resume or (message_topic and message_topic == active_topic):
                session.variables["workflow_suspended"] = False
                topic_conflict = False
            else:
                topic_conflict = True
        elif active and topic_conflict:
            session.variables["workflow_suspended"] = True
        history = self._context_history(session, request.message, active, topic_conflict)
        started = time.perf_counter()

        user_message = self._build_message(MessageRole.USER, request.message)
        self._sessions.append(session, user_message)
        self._audit.record(
            AuditEventType.MESSAGE.value,
            session.id,
            session.current_workflow_id,
            {"role": "user", "content": request.message},
        )

        intent = IntentType.QA.value
        intent_confidence = 0.0
        router_result: RouterResult | None = None

        if self._is_handoff_request(request.message):
            reply = self._handoff_reply(session)
            intent = IntentType.HUMAN_HANDOFF.value
            intent_confidence = 0.95
        elif request.message.strip() in WORKORDER_LOOKUP_WORDS:
            reply = self._workorder_lookup_reply(session)
            intent = IntentType.WORKFLOW.value
            intent_confidence = 0.9
        elif active is not None and not topic_conflict:
            reply = await self._workflow.handle(
                session,
                request.message,
                history=history,
                confirmed=None,
            )
            intent = IntentType.WORKFLOW.value
            intent_confidence = 0.96
        else:
            router_result = self._router.route(
                request.message,
                previous_intent=self._last_intent(session),
                has_history=bool(history),
            )
            session.variables["last_intent"] = router_result.intent.value
            intent = router_result.intent.value
            intent_confidence = router_result.confidence
            self._audit.record(
                AuditEventType.INTENT.value,
                session.id,
                session.current_workflow_id,
                {
                    "intent": router_result.intent.value,
                    "confidence": router_result.confidence,
                    "scores": router_result.scores,
                    "matched_keywords": router_result.matched_keywords,
                    "reason": router_result.reason,
                },
            )
            if router_result.intent == IntentType.WORKFLOW:
                reply = await self._workflow.handle(
                    session,
                    request.message,
                    history=history,
                    router_result=router_result,
                )
            else:
                reply = await self._qa.handle(
                    session,
                    request.message,
                    history=history,
                    router_result=router_result,
                )

        assistant_message = self._build_message(
            MessageRole.ASSISTANT,
            reply.content,
            citations=reply.citations,
            tool_calls=reply.tool_calls,
            confidence=reply.confidence,
            metadata={
                **reply.metadata,
                "requires_confirmation": reply.requires_confirmation,
                "intent": intent,
                "intent_confidence": intent_confidence,
                "suggested_actions": reply.suggested_actions,
            },
            trace=reply.trace,
        )
        self._sessions.append(session, assistant_message)
        self._audit.record(
            AuditEventType.MESSAGE.value,
            session.id,
            session.current_workflow_id,
            {
                "role": "assistant",
                "content": reply.content,
                "intent": intent,
                "citations": [citation.model_dump(mode="json") for citation in reply.citations],
                "requires_confirmation": reply.requires_confirmation,
                "workorder_id": reply.workorder.id if reply.workorder else None,
            },
        )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        workorder_snapshot = (
            reply.workorder.model_copy(deep=True) if reply.workorder is not None else None
        )
        response = ChatResponse(
            session_id=session.id,
            message=assistant_message,
            intent=intent,
            intent_confidence=round(float(intent_confidence), 4),
            requires_confirmation=reply.requires_confirmation,
            workorder=workorder_snapshot,
            suggested_actions=reply.suggested_actions,
            trace=reply.trace,
            metrics={
                "total_ms": elapsed_ms,
                "confidence": float(reply.confidence or 0.0),
            },
        )
        self._logger.info(
            f"chat: session={session.id} intent={intent} "
            f"workorder={reply.workorder.id if reply.workorder else '-'} {elapsed_ms}ms"
        )
        return response

    async def confirm(self, session_id: str, request: ConfirmRequest) -> ChatResponse:
        """处理工单确认/取消。"""
        session = self._sessions.get(session_id)
        workorder_id = session.current_workflow_id
        if not workorder_id:
            raise WorkflowStateError("当前会话没有待确认的工单")
        workorder = self._engine.store.get(workorder_id)
        if workorder.status != WorkOrderStatus.AWAITING_CONFIRM:
            raise WorkflowStateError(
                f"当前工单状态为 {workorder.status.value}，不在待确认状态"
            )

        history = list(session.messages)
        action_text = "确认提交" if request.action == "confirm" else "取消"
        user_message = self._build_message(
            MessageRole.USER,
            action_text,
            metadata={"action": request.action, "note": request.note},
        )
        self._sessions.append(session, user_message)
        self._audit.record(
            AuditEventType.CONFIRMATION.value,
            session.id,
            workorder_id,
            {"action": request.action, "note": request.note, "source": "api"},
        )

        started = time.perf_counter()
        reply = await self._workflow.handle(
            session,
            action_text,
            history=history,
            confirmed=request.action == "confirm",
        )
        assistant_message = self._build_message(
            MessageRole.ASSISTANT,
            reply.content,
            citations=reply.citations,
            tool_calls=reply.tool_calls,
            confidence=reply.confidence,
            metadata={
                **reply.metadata,
                "requires_confirmation": reply.requires_confirmation,
                "intent": IntentType.WORKFLOW.value,
                "confirmed": request.action,
                "suggested_actions": reply.suggested_actions,
            },
            trace=reply.trace,
        )
        self._sessions.append(session, assistant_message)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        workorder_snapshot = (
            reply.workorder.model_copy(deep=True) if reply.workorder is not None else None
        )
        return ChatResponse(
            session_id=session.id,
            message=assistant_message,
            intent=IntentType.WORKFLOW.value,
            intent_confidence=0.98,
            requires_confirmation=reply.requires_confirmation,
            workorder=workorder_snapshot,
            suggested_actions=reply.suggested_actions,
            trace=reply.trace,
            metrics={"total_ms": elapsed_ms, "confidence": float(reply.confidence or 0.0)},
        )

    def history(self, session_id: str) -> list[ChatMessage]:
        """读取会话历史消息。"""
        return self._sessions.get(session_id).messages

    # ------------------------------------------------------------------ 内部
    def _build_message(
        self,
        role: MessageRole,
        content: str,
        *,
        citations: list[Any] | None = None,
        tool_calls: list[Any] | None = None,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
        trace: list[Any] | None = None,
    ) -> ChatMessage:
        """构造消息对象。"""
        return ChatMessage(
            id=f"msg-{uuid.uuid4().hex[:10]}",
            role=role,
            content=content,
            timestamp=_now(),
            citations=list(citations or []),
            tool_calls=list(tool_calls or []),
            confidence=confidence,
            metadata=dict(metadata or {}),
            trace=list(trace or []),
        )

    def _active_workorder(self, session: ChatSession) -> Any | None:
        """返回会话中未结束的工单。"""
        workorder_id = session.current_workflow_id
        if not workorder_id:
            return None
        try:
            workorder = self._engine.store.get(workorder_id)
        except Exception:  # noqa: BLE001 - 工单可能已被清理
            session.current_workflow_id = None
            return None
        if workorder.status in TERMINAL_STATUSES:
            return None
        return workorder

    @staticmethod
    def _detect_topic(text: str) -> str | None:
        """识别当前问题所属的校园话题。"""
        for topic, hints in TOPIC_GROUPS:
            if any(hint in text for hint in hints):
                return topic
        return None

    @staticmethod
    def _is_context_follow_up(text: str) -> bool:
        """判断是否是依赖上一轮的短追问，而不是独立新问题。"""
        cleaned = text.strip()
        if not cleaned:
            return False
        if len(cleaned) <= 12:
            return True
        return cleaned.endswith(("呢", "吗", "么")) or cleaned.startswith(
            ("那", "这", "它", "他们", "还有", "如果")
        )

    def _context_history(
        self,
        session: ChatSession,
        text: str,
        active: Any | None,
        topic_conflict: bool = False,
    ) -> list[ChatMessage]:
        """按话题裁剪上下文：新话题重置，短追问保留最近几轮。

        会话历史仍完整落库；这里只控制送给 Router/QA 的上下文窗口，
        避免“补办卡后问奖学金”被上一话题带偏。
        """
        history = list(session.messages)
        if active is not None and not topic_conflict:
            return history

        current_topic = self._detect_topic(text)
        previous_topic = session.variables.get("last_topic")
        if current_topic:
            session.variables["last_topic"] = current_topic
            if previous_topic and previous_topic != current_topic:
                return []
            return history[-8:]
        if previous_topic and self._is_context_follow_up(text):
            return history[-8:]
        if previous_topic:
            # 没有明确话题、也不是短追问：当作独立问题，不继承旧话题。
            return []
        return history[-8:]

    def _last_intent(self, session: ChatSession) -> IntentType | None:
        """读取上一轮意图。"""
        raw = session.variables.get("last_intent")
        if not raw:
            return None
        try:
            return IntentType(str(raw))
        except ValueError:
            return None

    @staticmethod
    def _is_handoff_request(text: str) -> bool:
        """判断是否显式要求转人工。"""
        return any(word in text for word in HANDOFF_WORDS)

    def _handoff_reply(self, session: ChatSession) -> AgentReply:
        """生成转人工回复，并保留上下文。"""
        workorder = self._active_workorder(session)
        suffix = (
            f"\n\n当前工单（{workorder.receipt_number or workorder.id}）的上下文已保留。"
            if workorder
            else "\n\n当前会话上下文已保留。"
        )
        content = (
            "已记录你的转人工请求。\n\n"
            "- 对接部门：学生服务大厅\n"
            "- 联系电话：0512-6716-0000\n"
            "- 服务时间：工作日 8:30-17:00\n"
            f"{suffix}"
        )
        self._audit.record(
            AuditEventType.HANDOFF.value,
            session.id,
            workorder.id if workorder else None,
            {"source": "explicit_request"},
        )
        return AgentReply(
            content=content,
            confidence=0.95,
            metadata={
                "intent": IntentType.HUMAN_HANDOFF.value,
                "handoff": True,
                "workorder_id": workorder.id if workorder else None,
            },
            suggested_actions=[],
            trace=[],
        )

    def _workorder_lookup_reply(self, session: ChatSession) -> AgentReply:
        """快捷查询当前会话的最近一张工单。"""
        orders = [
            order
            for order in self._engine.store.list()
            if order.session_id == session.id
        ]
        if not orders:
            return AgentReply(
                content="当前会话还没有工单。可以告诉我“我要补办校园卡”来发起办理。",
                confidence=0.9,
                metadata={"intent": IntentType.WORKFLOW.value},
                suggested_actions=["我要补办校园卡"],
            )
        latest = orders[0]
        lines = [
            f"最近一张工单：**{latest.receipt_number or latest.id}**",
            "",
            f"- 流程：{latest.workflow_type}",
            f"- 状态：{latest.status.value}",
            f"- 更新时间：{latest.updated_at.astimezone().strftime('%Y-%m-%d %H:%M')}",
        ]
        if latest.result and latest.result.get("location"):
            lines.append(f"- 取卡地点：{latest.result['location']}")
        return AgentReply(
            content="\n".join(lines),
            confidence=0.9,
            metadata={"intent": IntentType.WORKFLOW.value},
            workorder=latest,
            suggested_actions=["查看工单"],
        )
