"""校园卡补办全链路测试。"""

from __future__ import annotations

import asyncio

from app.core.enums import WorkOrderStatus
from app.deps import AppContainer


def _start_to_confirm(container: AppContainer, send, student: str, campus: str):
    """辅助：发起补办并补全参数，返回第二阶段响应。"""
    first = send("我要补办校园卡")
    assert first.workorder is not None
    second = send(f"{student}，{campus}", first.session_id)
    return first, second


def test_full_success_flow(container: AppContainer, send, confirm) -> None:
    """已挂失、无欠费时一次对话完成补办并生成回执。"""
    first, second = _start_to_confirm(container, send, "2025001002", "独墅湖")
    assert first.workorder.status == WorkOrderStatus.AWAITING_INPUT
    assert second.requires_confirmation is True
    assert second.workorder.status == WorkOrderStatus.AWAITING_CONFIRM

    result = confirm(first.session_id, "confirm")
    assert result.workorder is not None
    assert result.workorder.status == WorkOrderStatus.COMPLETED
    assert result.workorder.receipt_number.startswith("CARD")
    assert result.workorder.result
    assert "独墅湖校区" in result.workorder.result["location"]
    assert "回执" in result.message.content


def test_handoff_queue_claim_and_resolve(client) -> None:
    """超时转人工后进入坐席队列，可认领并办结。"""
    session = client.post("/api/v1/sessions", json={}).json()
    client.post(
        "/api/v1/chat/send",
        json={"session_id": session["id"], "message": "我要补办校园卡"},
    )
    transferred = client.post(
        "/api/v1/chat/send",
        json={"session_id": session["id"], "message": "2025000999，独墅湖"},
    ).json()
    assert transferred["workorder"]["status"] == "transferred_human"

    queue = client.get("/api/v1/handoff/queue").json()
    assert queue["count"] >= 1
    order = next(item for item in queue["items"] if item["session_id"] == session["id"])
    claimed = client.post(f"/api/v1/handoff/{order['id']}/claim")
    assert claimed.status_code == 200
    resolved = client.post(
        f"/api/v1/handoff/{order['id']}/resolve",
        json={"note": "已联系网络中心并回电学生", "result": "completed"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "completed"


def test_leave_flow_needs_two_approvals(client) -> None:
    """请假超过 3 天：辅导员 + 学院两次审批后才能提交。"""
    session = client.post("/api/v1/sessions", json={}).json()
    client.post(
        "/api/v1/chat/send",
        json={"session_id": session["id"], "message": "我要请假"},
    )
    waiting = client.post(
        "/api/v1/chat/send",
        json={"session_id": session["id"], "message": "2025001001，独墅湖，5天，病假"},
    ).json()
    assert waiting["workorder"]["status"] == "awaiting_approval"
    order_id = waiting["workorder"]["id"]

    first = client.post(f"/api/v1/approvals/{order_id}/approve", json={"note": "同意"})
    assert first.status_code == 200
    assert first.json()["status"] == "awaiting_approval"

    second = client.post(f"/api/v1/approvals/{order_id}/approve", json={"note": "学院同意"})
    assert second.status_code == 200
    assert second.json()["status"] == "completed"
    assert second.json()["workorder"]["receipt_number"].startswith("LVE")

    returned = client.post(f"/api/v1/approvals/{order_id}/return")
    assert returned.status_code == 200
    assert returned.json()["returned"] is True
    assert returned.json()["leave_status"] == "returned"


def test_leave_can_be_withdrawn(client) -> None:
    """学生可在审批前撤回请假申请。"""
    session = client.post("/api/v1/sessions", json={}).json()
    client.post("/api/v1/chat/send", json={"session_id": session["id"], "message": "我要请假"})
    waiting = client.post(
        "/api/v1/chat/send",
        json={"session_id": session["id"], "message": "2025001001，独墅湖，2天，事假"},
    ).json()
    assert waiting["workorder"]["status"] == "awaiting_approval"
    order_id = waiting["workorder"]["id"]
    withdrawn = client.post(f"/api/v1/approvals/{order_id}/withdraw")
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "cancelled"


def test_network_repair_flow(container: AppContainer, send, confirm) -> None:
    """第二条 DSL 流程：网络报修，确认后生成 RPR 回执。"""
    first = send("我要报修网络")
    assert first.workorder is not None
    second = send("2025001001，独墅湖，上不了网", first.session_id)
    assert second.workorder is not None
    assert second.workorder.workflow_type == "network_repair"
    assert second.workorder.status == WorkOrderStatus.AWAITING_CONFIRM
    result = confirm(first.session_id, "confirm")
    assert result.workorder is not None
    assert result.workorder.status == WorkOrderStatus.COMPLETED
    assert result.workorder.receipt_number.startswith("RPR")
    assert "网络报修" in result.message.content


def test_auto_report_loss(container: AppContainer, send) -> None:
    """未挂失学号应先自动挂失，再进入确认。"""
    first, second = _start_to_confirm(container, send, "2025001001", "天赐庄")
    node_ids = [record.node_id for record in second.workorder.node_history]
    assert "report_loss" in node_ids
    status = asyncio.run(container.mock_service.query_loss_status("2025001001"))
    assert status["lost"] is True
    assert second.workorder.status == WorkOrderStatus.AWAITING_CONFIRM


def test_arrears_blocks_flow(container: AppContainer, send) -> None:
    """存在欠费时提示金额并中止，不进入确认。"""
    _, second = _start_to_confirm(container, send, "2025001003", "阳澄湖")
    assert second.workorder.status == WorkOrderStatus.FAILED
    assert "35.50" in second.message.content
    assert "欠费" in second.message.content
    assert second.requires_confirmation is False


def test_invalid_student_stops(container: AppContainer, send) -> None:
    """不存在的学号应提示错误并结束，不继续流程。"""
    _, second = _start_to_confirm(container, send, "2025009999", "独墅湖")
    assert second.workorder.status == WorkOrderStatus.FAILED
    assert "2025009999" in second.message.content
    node_ids = [record.node_id for record in second.workorder.node_history]
    assert "query_loss" not in node_ids


def test_tool_timeout_transfers_human(container: AppContainer, send) -> None:
    """故障注入学号应重试一次后转人工，并保留上下文。"""
    first, second = _start_to_confirm(container, send, "2025000999", "独墅湖")
    assert second.workorder.status == WorkOrderStatus.TRANSFERRED_HUMAN
    assert "超时" in second.message.content
    assert second.workorder.user_inputs["student_id"] == "2025000999"
    assert second.workorder.user_inputs["campus"] == "独墅湖"

    logs = container.audit.query_workorder(second.workorder.id)
    failures = [
        event
        for event in logs
        if event.event_type == "tool_call"
        and event.payload.get("tool") == "student.query_profile"
        and event.payload.get("success") is False
    ]
    assert len(failures) == 2


def test_cancel_does_not_submit(container: AppContainer, send, confirm) -> None:
    """取消确认后工单应为取消状态，且不调用提交工具。"""
    first, _ = _start_to_confirm(container, send, "2025001002", "独墅湖")
    result = confirm(first.session_id, "cancel")
    assert result.workorder.status == WorkOrderStatus.CANCELLED
    node_ids = [record.node_id for record in result.workorder.node_history]
    assert "submit_order" not in node_ids
    assert "取消" in result.message.content


def test_idempotent_submission(container: AppContainer, send, confirm) -> None:
    """同一学号同一天重复提交应返回原回执，不新增工单。"""
    first, _ = _start_to_confirm(container, send, "2025001002", "独墅湖")
    completed = confirm(first.session_id, "confirm")
    receipt = completed.workorder.receipt_number
    original_id = completed.workorder.id
    count_after_first = len(container.workorder_store.list())
    assert count_after_first == 1

    second_start, _ = _start_to_confirm(container, send, "2025001002", "独墅湖")
    duplicate = confirm(second_start.session_id, "confirm")
    assert duplicate.workorder is not None
    assert duplicate.workorder.receipt_number == receipt
    assert duplicate.workorder.id == original_id
    assert "没有重复生成" in duplicate.message.content
    assert len(container.workorder_store.list()) == count_after_first
    assert (
        len(
            [
                order
                for order in container.workorder_store.list()
                if order.receipt_number == receipt
            ]
        )
        == 1
    )


def test_parameter_validation(container: AppContainer, send) -> None:
    """学号位数不对时应提示重新输入并保持待补充状态。"""
    first = send("我要补办校园卡")
    invalid = send("2025001，独墅湖", first.session_id)
    assert invalid.workorder.status == WorkOrderStatus.AWAITING_INPUT
    assert "10 位" in invalid.message.content

    letters = send("abc，独墅湖", first.session_id)
    assert letters.workorder.status == WorkOrderStatus.AWAITING_INPUT


def test_workorder_audit_trail(container: AppContainer, send, confirm) -> None:
    """完成后应能按工单查到完整审计轨迹。"""
    first, _ = _start_to_confirm(container, send, "2025001002", "独墅湖")
    completed = confirm(first.session_id, "confirm")
    workorder_id = completed.workorder.id

    events = container.audit.query_workorder(workorder_id)
    event_types = {event.event_type for event in events}
    assert "tool_call" in event_types
    assert "node_transition" in event_types
    assert "confirmation" in event_types
    assert any(
        event.payload.get("tool") == "card.submit_reissue_order"
        for event in events
        if event.event_type == "tool_call"
    )
