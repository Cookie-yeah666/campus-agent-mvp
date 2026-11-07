"""工作流引擎测试：暂停、恢复、分支与断点持久化。"""

from __future__ import annotations

import asyncio

import pytest

from app.core.enums import WorkOrderStatus
from app.core.exceptions import WorkflowStateError
from app.deps import AppContainer
from app.memory.store import WorkOrderStore


def test_start_pauses_for_parameters(container: AppContainer) -> None:
    """启动后应停在参数抽取节点。"""
    result = asyncio.run(
        container.engine.start("card_reissue", "cs-engine-test", "我要补办校园卡")
    )
    assert result.finished is False
    assert result.workorder.status == WorkOrderStatus.AWAITING_INPUT
    assert result.workorder.current_node == "extract_params"
    assert "学号" in result.message
    assert result.workorder.node_history


def test_resume_reaches_confirmation(container: AppContainer) -> None:
    """补齐参数后应完成校验并停在人工确认节点。"""
    first = asyncio.run(
        container.engine.start("card_reissue", "cs-engine-test", "我要补办校园卡")
    )
    result = asyncio.run(
        container.engine.resume(first.workorder.id, "2025001002，独墅湖")
    )
    assert result.requires_confirmation is True
    assert result.workorder.status == WorkOrderStatus.AWAITING_CONFIRM
    assert "20 元" in result.message
    node_ids = [record.node_id for record in result.workorder.node_history]
    assert "query_profile" in node_ids
    assert "query_loss" in node_ids
    assert "query_balance" in node_ids
    assert "query_slots" in node_ids
    assert "confirm" in node_ids


def test_invalid_student_branch(container: AppContainer) -> None:
    """学号不存在时应走失败分支并结束。"""
    first = asyncio.run(
        container.engine.start("card_reissue", "cs-engine-test", "我要补办校园卡")
    )
    result = asyncio.run(
        container.engine.resume(first.workorder.id, "2025009999 独墅湖")
    )
    assert result.finished is True
    assert result.workorder.status == WorkOrderStatus.FAILED
    assert "2025009999" in result.message


def test_state_snapshot_and_persistence(container: AppContainer) -> None:
    """暂停状态应可查询，并已落盘可恢复。"""
    first = asyncio.run(
        container.engine.start("card_reissue", "cs-engine-test", "我要补办校园卡")
    )
    asyncio.run(container.engine.resume(first.workorder.id, "2025001002 独墅湖"))

    state = container.engine.get_state(first.workorder.id)
    assert state.status == WorkOrderStatus.AWAITING_CONFIRM.value
    assert state.current_node == "confirm"
    assert state.variables["student_id"] == "2025001002"

    reloaded = WorkOrderStore(container.settings)
    persisted = reloaded.get(first.workorder.id)
    assert persisted.status == WorkOrderStatus.AWAITING_CONFIRM
    assert persisted.receipt_number == ""


def test_unknown_workflow_type(container: AppContainer) -> None:
    """未注册流程应抛出明确异常。"""
    with pytest.raises(WorkflowStateError):
        asyncio.run(
            container.engine.start("unknown_flow", "cs-test", "办理业务")
        )
