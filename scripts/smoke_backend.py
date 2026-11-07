"""后端端到端冒烟脚本（不启动 HTTP）。"""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.deps import AppContainer  # noqa: E402
from app.models.schema import ChatRequest, ConfirmRequest, WorkOrderStatus  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "_smoke_data"


def make_container() -> AppContainer:
    """使用独立数据目录构建容器。"""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    settings = Settings(
        data_dir=DATA_DIR,
        llm_simulate_delay=False,
        tool_simulate_delay=False,
    )
    return AppContainer(settings)


async def ask(container: AppContainer, session_id: str | None, text: str) -> str:
    """发送一条消息并打印关键信息。"""
    response = await container.chat_service.send(
        ChatRequest(session_id=session_id, message=text)
    )
    print(f"\n=== 用户：{text}")
    print(f"意图：{response.intent} ({response.intent_confidence:.2f})")
    print(f"回复：{response.message.content}")
    if response.message.citations:
        print("引用：")
        for citation in response.message.citations:
            print(f"  - {citation.doc_title} / {citation.chapter} / {citation.score:.2f}")
    if response.workorder:
        print(
            f"工单：{response.workorder.id} 状态={response.workorder.status.value} "
            f"回执={response.workorder.receipt_number or '-'}"
        )
    return response.session_id


async def main() -> None:
    """执行全部冒烟场景。"""
    container = make_container()
    print("KB:", container.knowledge.stats())
    print("tools:", container.tool_registry.names)

    session_id = await ask(container, None, "奖学金申请需要什么材料？")
    await ask(container, session_id, "校园卡补办要多少钱？")
    await ask(container, session_id, "学校附近有什么好吃的火锅")

    workflow_session = await ask(container, None, "我要补办校园卡")
    await ask(container, workflow_session, "2025001002，独墅湖")

    session = container.session_manager.get(workflow_session)
    if session.current_workflow_id:
        workorder = container.workorder_store.get(session.current_workflow_id)
        print(f"待确认工单状态：{workorder.status.value}")
        response = await container.chat_service.confirm(
            workflow_session, ConfirmRequest(action="confirm")
        )
        print(f"\n=== 确认后：{response.message.content}")
        print(
            f"状态={response.workorder.status.value} 回执={response.workorder.receipt_number}"
            if response.workorder
            else "无工单"
        )

    # 幂等：同一天同一学号再次办理
    duplicate_session = await ask(container, None, "我要补办校园卡")
    await ask(container, duplicate_session, "2025001002 独墅湖")
    dup = await container.chat_service.confirm(
        duplicate_session, ConfirmRequest(action="confirm")
    )
    print(f"\n=== 重复提交：{dup.message.content}")
    if dup.workorder:
        print(f"回执={dup.workorder.receipt_number} duplicate={dup.workorder.duplicate_of}")

    # 欠费
    arrears_session = await ask(container, None, "我要补办校园卡")
    arrears = await ask(container, arrears_session, "2025001003 阳澄湖")
    print(f"欠费会话当前工单：{arrears}")

    # 超时
    timeout_session = await ask(container, None, "我要补办校园卡")
    await ask(container, timeout_session, "2025000999 独墅湖")

    # 评测
    report = container.evaluation.run()
    print(
        f"\n评测：Recall@5={report.recall_at_5} MRR@5={report.mrr_at_5} "
        f"avg={report.avg_latency_ms}ms p95={report.p95_latency_ms}ms"
    )
    misses = [item.query for item in report.details if not item.hit]
    print("未命中：", misses)

    print(
        f"\n统计：工单 {container.workorder_store.count()} / "
        f"会话 {container.session_store.count()} / 审计 {container.audit.count()}"
    )
    print("工单状态：", container.workorder_store.counts())


if __name__ == "__main__":
    asyncio.run(main())
