"""节点式工作流引擎。

引擎负责：工单创建、节点循环、边跳转、暂停/恢复、持久化与审计；
节点自身只关心业务语义。支持断点恢复：暂停状态落盘后可从当前节点继续。
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.core.enums import AuditEventType, NodeOutcome, NodeStatus, NodeType, WorkOrderStatus
from app.core.exceptions import WorkflowStateError
from app.models.domain import (
    NodeResult,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowRunResult,
    WorkflowState,
)
from app.models.schema import NodeExecutionRecord, WorkOrder
from app.workflow import conditions  # noqa: F401  确保条件函数完成注册
from app.workflow.nodes import CANCEL_WORDS, CONFIRM_WORDS, execute_node

TERMINAL_STATUSES = {
    WorkOrderStatus.COMPLETED,
    WorkOrderStatus.CANCELLED,
    WorkOrderStatus.FAILED,
    WorkOrderStatus.TRANSFERRED_HUMAN,
}


def _now() -> datetime:
    """当前 UTC 时间。"""
    return datetime.now(timezone.utc)


class WorkflowEngine:
    """通用工作流引擎。"""

    def __init__(
        self,
        definitions: dict[str, WorkflowDefinition],
        tool_registry: Any,
        workorder_store: Any,
        audit: Any,
        idempotency: Any,
        settings: Settings,
        logger: Any,
    ) -> None:
        self._definitions = definitions
        self._tools = tool_registry
        self._store = workorder_store
        self._audit = audit
        self._idempotency = idempotency
        self._settings = settings
        self._logger = logger

    @property
    def store(self) -> Any:
        """工单存储（供 Agent 查询）。"""
        return self._store

    def get_definition(self, workflow_type: str) -> WorkflowDefinition:
        """获取流程定义。

        Raises:
            WorkflowStateError: 流程类型未注册。
        """
        definition = self._definitions.get(workflow_type)
        if definition is None:
            raise WorkflowStateError(f"未注册的工作流类型: {workflow_type}")
        return definition

    async def start(
        self,
        workflow_type: str,
        session_id: str,
        initial_input: str,
    ) -> WorkflowRunResult:
        """创建工单并执行到暂停或结束。"""
        definition = self.get_definition(workflow_type)
        workorder = WorkOrder(
            id=f"wo-{uuid.uuid4().hex[:12]}",
            workflow_type=workflow_type,
            definition_version=definition.version,
            definition_snapshot=definition.model_dump(mode="json"),
            status=WorkOrderStatus.IN_PROGRESS,
            current_node=definition.start_node,
            session_id=session_id,
            idempotency_key="",
        )
        self._store.save(workorder)
        ctx = self._build_context(workorder, session_id, initial_input, definition, confirmed=None)
        self._audit.record(
            AuditEventType.NODE_TRANSITION.value,
            session_id,
            workorder.id,
            {"event": "workflow_started", "workflow_type": workflow_type},
        )
        self._logger.info(f"工作流启动: {workflow_type} / {workorder.id} / session={session_id}")
        return await self._run(ctx, definition.start_node)

    async def resume(
        self,
        workorder_id: str,
        user_input: str,
        *,
        confirmed: bool | None = None,
    ) -> WorkflowRunResult:
        """从暂停节点恢复工单。"""
        workorder = self._store.get(workorder_id)
        if workorder.definition_snapshot:
            definition = WorkflowDefinition.model_validate(workorder.definition_snapshot)
        else:
            definition = self.get_definition(workorder.workflow_type)
        if workorder.status in TERMINAL_STATUSES:
            return WorkflowRunResult(
                workorder=workorder,
                message=self._finished_message(workorder),
                finished=True,
            )

        ctx = self._build_context(
            workorder,
            workorder.session_id or "",
            user_input,
            definition,
            confirmed=confirmed,
        )
        node = definition.get_node(workorder.current_node)
        if node is None:
            raise WorkflowStateError(f"当前节点不存在: {workorder.current_node}")

        normalized = user_input.strip().lower()
        if node.node_type == NodeType.CONFIRMATION and ctx.confirmed is None:
            if normalized in CONFIRM_WORDS:
                ctx.confirmed = True
            elif normalized in CANCEL_WORDS:
                ctx.confirmed = False
        if node.node_type == NodeType.PARAMETER_EXTRACT and normalized in CANCEL_WORDS:
            workorder.status = WorkOrderStatus.CANCELLED
            workorder.result = {"reason": "cancelled"}
            workorder.updated_at = _now()
            self._store.save(workorder)
            return WorkflowRunResult(
                workorder=workorder,
                message="已取消本次校园卡补办申请。",
                finished=True,
            )

        self._audit.record(
            AuditEventType.NODE_TRANSITION.value,
            workorder.session_id or "",
            workorder.id,
            {"event": "workflow_resumed", "node": node.id, "input": user_input},
        )
        return await self._run(ctx, node.id)

    def get_state(self, workorder_id: str) -> WorkflowState:
        """返回工单状态快照。"""
        workorder = self._store.get(workorder_id)
        return WorkflowState(
            workorder_id=workorder.id,
            workflow_type=workorder.workflow_type,
            status=workorder.status.value,
            current_node=workorder.current_node,
            variables=dict(workorder.user_inputs),
            node_history=list(workorder.node_history),
        )

    # ------------------------------------------------------------------ 内部
    def _build_context(
        self,
        workorder: WorkOrder,
        session_id: str,
        user_input: str,
        definition: WorkflowDefinition,
        *,
        confirmed: bool | None,
    ) -> WorkflowContext:
        """构造节点执行上下文。"""
        return WorkflowContext(
            workorder=workorder,
            session_id=session_id,
            user_input=user_input,
            variables=dict(workorder.user_inputs),
            settings=self._settings,
            tool_registry=self._tools,
            audit=self._audit,
            idempotency=self._idempotency,
            workorder_store=self._store,
            logger=self._logger,
            definition=definition,
            confirmed=confirmed,
        )

    async def _run(self, ctx: WorkflowContext, start_node: str) -> WorkflowRunResult:
        """节点循环：执行到暂停、结束或失败。"""
        definition = ctx.definition
        assert definition is not None
        current = start_node
        workorder = ctx.workorder

        for _ in range(self._settings.max_workflow_steps):
            node = definition.get_node(current)
            if node is None:
                return self._fail(ctx, f"节点不存在: {current}")

            started_at = _now()
            started_clock = time.perf_counter()
            result = await execute_node(ctx, node, self)
            duration_ms = int((time.perf_counter() - started_clock) * 1000)

            record = NodeExecutionRecord(
                node_id=node.id,
                node_name=node.name,
                node_type=node.node_type.value,
                inputs={"user_input": ctx.user_input},
                outputs=self._safe_outputs(result.data),
                started_at=started_at,
                duration_ms=duration_ms,
                status=(
                    NodeStatus.FAILED.value
                    if result.outcome in {NodeOutcome.FAIL, NodeOutcome.HANDOFF}
                    else NodeStatus.SUCCESS.value
                ),
                error=result.error,
            )
            workorder.node_history.append(record)
            self._audit.record(
                AuditEventType.NODE_TRANSITION.value,
                ctx.session_id,
                workorder.id,
                {
                    "node_id": node.id,
                    "node_name": node.name,
                    "node_type": node.node_type.value,
                    "outcome": result.outcome.value,
                    "duration_ms": duration_ms,
                    "error": result.error,
                },
            )

            if result.outcome == NodeOutcome.CONTINUE:
                if not result.next_node:
                    return self._fail(ctx, f"节点 {node.id} 未指定下一节点")
                current = result.next_node
                continue

            if result.outcome == NodeOutcome.PAUSE:
                if result.data.get("approval_role"):
                    workorder.status = WorkOrderStatus.AWAITING_APPROVAL
                else:
                    workorder.status = (
                        WorkOrderStatus.AWAITING_CONFIRM
                        if result.requires_confirmation
                        else WorkOrderStatus.AWAITING_INPUT
                    )
                workorder.current_node = node.id
                workorder.updated_at = _now()
                self._store.save(workorder)
                self._logger.info(f"工单暂停: {workorder.id} @ {node.id}")
                return WorkflowRunResult(
                    workorder=workorder,
                    message=result.message,
                    requires_confirmation=result.requires_confirmation,
                    suggested_actions=result.suggested_actions,
                    finished=False,
                    trace=ctx.trace,
                )

            if result.outcome == NodeOutcome.FINISH:
                if result.data.get("duplicate"):
                    duplicate = await self._finish_duplicate(ctx, node, result)
                    if duplicate is not None:
                        return duplicate
                workorder.current_node = node.id
                workorder.updated_at = _now()
                if workorder.status not in TERMINAL_STATUSES:
                    workorder.status = WorkOrderStatus.COMPLETED
                if workorder.result is None:
                    workorder.result = dict(result.data) or None
                self._store.save(workorder)
                self._logger.info(f"工单结束: {workorder.id} status={workorder.status.value}")
                return WorkflowRunResult(
                    workorder=workorder,
                    message=result.message,
                    suggested_actions=result.suggested_actions,
                    finished=True,
                    trace=ctx.trace,
                )

            if result.outcome == NodeOutcome.HANDOFF:
                workorder.status = WorkOrderStatus.TRANSFERRED_HUMAN
                workorder.current_node = node.id
                workorder.error_message = result.error
                workorder.handoff_reason = result.error or "tool_failure"
                workorder.handoff_at = _now()
                workorder.updated_at = _now()
                self._store.save(workorder)
                self._audit.record(
                    AuditEventType.HANDOFF.value,
                    ctx.session_id,
                    workorder.id,
                    {"reason": result.error or "tool_failure"},
                )
                return WorkflowRunResult(
                    workorder=workorder,
                    message=result.message,
                    finished=True,
                    trace=ctx.trace,
                )

            # FAIL
            workorder.status = WorkOrderStatus.FAILED
            workorder.current_node = node.id
            workorder.error_message = result.error or "工作流执行失败"
            workorder.updated_at = _now()
            self._store.save(workorder)
            return WorkflowRunResult(
                workorder=workorder,
                message=result.message or "流程执行失败，请稍后重试。",
                finished=True,
                trace=ctx.trace,
            )

        return self._fail(ctx, "工作流执行步数超过上限，可能存在循环")

    async def _finish_duplicate(
        self,
        ctx: WorkflowContext,
        node: Any,
        result: NodeResult,
    ) -> WorkflowRunResult | None:
        """处理幂等命中：删除本次草稿工单，返回原工单。"""
        original_id = str(result.data.get("original_id", ""))
        if not original_id:
            return None
        try:
            original = self._store.get(original_id)
        except Exception:  # noqa: BLE001 - 原工单可能已被清理
            return None
        self._store.delete(ctx.workorder.id)
        self._audit.record(
            AuditEventType.IDEMPOTENCY.value,
            ctx.session_id,
            original.id,
            {
                "duplicate_workorder": ctx.workorder.id,
                "receipt": original.receipt_number,
                "action": "merged_into_existing",
            },
        )
        return WorkflowRunResult(
            workorder=original,
            message=result.message,
            finished=True,
            duplicate=True,
            suggested_actions=["查看工单"],
            trace=ctx.trace,
        )

    def _fail(self, ctx: WorkflowContext, message: str) -> WorkflowRunResult:
        """把流程标记为失败并返回。"""
        workorder = ctx.workorder
        workorder.status = WorkOrderStatus.FAILED
        workorder.error_message = message
        workorder.updated_at = _now()
        self._store.save(workorder)
        self._logger.error(f"工作流失败: {workorder.id} - {message}")
        return WorkflowRunResult(
            workorder=workorder,
            message=f"流程执行失败：{message}",
            finished=True,
            trace=ctx.trace,
        )

    @staticmethod
    def _safe_outputs(data: dict[str, Any]) -> dict[str, Any]:
        """裁剪节点输出，避免审计日志过大。"""
        try:
            encoded = json.dumps(data, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return {"summary": str(data)[:200]}
        if len(encoded) <= 800:
            return data
        return {"summary": encoded[:800] + "…"}

    @staticmethod
    def _finished_message(workorder: WorkOrder) -> str:
        """已结束工单的提示文案。"""
        if workorder.status == WorkOrderStatus.COMPLETED and workorder.receipt_number:
            return f"该工单已完成，回执编号：{workorder.receipt_number}。"
        if workorder.status == WorkOrderStatus.CANCELLED:
            return "该工单已取消。"
        if workorder.status == WorkOrderStatus.TRANSFERRED_HUMAN:
            return "该工单已转人工处理，请留意工作人员联系。"
        return "该工单已结束，如需帮助请重新发起。"
