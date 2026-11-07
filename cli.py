"""命令行交互入口。

与 Web 共用 ``ChatService``，不重复实现业务逻辑。
运行：``python cli.py``
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from app.config import get_settings
from app.core.exceptions import CampusAgentError
from app.deps import AppContainer, build_container
from app.llm.prompt_templates import HELP_MESSAGE, WELCOME_MESSAGE
from app.models.schema import ChatRequest, ChatResponse, ConfirmRequest, WorkOrderStatus

# 开启 Windows 终端的 ANSI 颜色
if os.name == "nt":
    os.system("")


class Color:
    """终端颜色。"""

    USER = "\033[96m"
    ASSISTANT = "\033[92m"
    SYSTEM = "\033[93m"
    ERROR = "\033[91m"
    CYAN = "\033[36m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def plain(text: str) -> str:
    """去掉终端不需要的 Markdown 标记。"""
    return text.replace("**", "").replace("`", "")


def print_banner(container: AppContainer) -> None:
    """打印欢迎语与运行信息。"""
    settings = container.settings
    print(f"{Color.BOLD}{settings.app_name}{Color.RESET} v{settings.app_version}")
    print(f"{Color.DIM}模型：{settings.llm_model_name} · 知识库："
          f"{len(container.knowledge.documents)} 篇 / {len(container.knowledge.chunks)} 块"
          f"{Color.RESET}")
    print()
    print(plain(WELCOME_MESSAGE))
    print()


def print_reply(response: ChatResponse) -> None:
    """打印助手回复、引用、工具调用与工单信息。"""
    message = response.message
    print(f"\n{Color.ASSISTANT}知行 ▸{Color.RESET} {plain(message.content)}\n")
    if message.citations:
        print(f"{Color.DIM}引用来源：{Color.RESET}")
        for index, citation in enumerate(message.citations, start=1):
            number = citation.doc_number or "无文号"
            print(
                f"  {Color.CYAN}[{index}]{Color.RESET} 《{citation.doc_title}》"
                f" · {citation.chapter}（{number}，score={citation.score:.2f}）"
            )
            print(f"      {Color.DIM}{citation.content_snippet}{Color.RESET}")
        print()
    if message.tool_calls:
        print(f"{Color.DIM}工具调用：{Color.RESET}")
        for call in message.tool_calls:
            status = "成功" if call.success else "失败"
            print(f"  · {call.tool_name} [{status}] {call.latency_ms}ms")
        print()
    if message.confidence is not None:
        print(f"{Color.DIM}置信度：{message.confidence:.2f}{Color.RESET}")
    if response.workorder:
        order = response.workorder
        print(
            f"{Color.DIM}工单：{order.id} · 状态 {order.status.value}"
            f"{' · 回执 ' + order.receipt_number if order.receipt_number else ''}{Color.RESET}"
        )
    print()


async def handle_confirmation(
    container: AppContainer,
    session_id: str,
) -> ChatResponse | None:
    """在终端询问确认/取消。"""
    answer = (await asyncio.to_thread(input, "确认提交？[y/n] ")).strip().lower()
    if answer not in {"y", "yes", "确认", "n", "no", "取消"}:
        print(f"{Color.SYSTEM}已跳过，输入 /history 可查看工单状态。{Color.RESET}")
        return None
    action = "confirm" if answer in {"y", "yes", "确认"} else "cancel"
    return await container.chat_service.confirm(session_id, ConfirmRequest(action=action))


async def show_history(container: AppContainer, session_id: str) -> None:
    """打印当前会话历史。"""
    try:
        messages = container.chat_service.history(session_id)
    except CampusAgentError as exc:
        print(f"{Color.ERROR}{exc.message}{Color.RESET}")
        return
    if not messages:
        print(f"{Color.SYSTEM}当前会话还没有消息。{Color.RESET}")
        return
    for message in messages:
        role = "你" if message.role.value == "user" else "知行"
        color = Color.USER if message.role.value == "user" else Color.ASSISTANT
        print(f"{color}{role} ▸{Color.RESET} {message.content[:200]}")
        if message.citations:
            print(f"  {Color.DIM}引用 {len(message.citations)} 条{Color.RESET}")


async def show_audit(container: AppContainer, session_id: str) -> None:
    """打印当前会话审计轨迹。"""
    logs = container.audit.query_session(session_id)
    if not logs:
        print(f"{Color.SYSTEM}当前会话还没有审计记录。{Color.RESET}")
        return
    print(f"{Color.DIM}共 {len(logs)} 条审计事件：{Color.RESET}")
    for log in logs[-40:]:
        timestamp = log.timestamp.astimezone().strftime("%H:%M:%S")
        summary = str(log.payload.get("tool") or log.payload.get("node_name") or "")
        if log.event_type == "message":
            summary = f"{log.payload.get('role')}: {str(log.payload.get('content'))[:30]}"
        print(
            f"  {Color.DIM}{timestamp}{Color.RESET} {Color.CYAN}{log.event_type}{Color.RESET}"
            f" {summary}"
        )


async def show_workorders(container: AppContainer) -> None:
    """打印最近工单。"""
    orders = container.workorder_store.list()[:10]
    if not orders:
        print(f"{Color.SYSTEM}还没有工单。{Color.RESET}")
        return
    for order in orders:
        print(
            f"  {Color.CYAN}{order.receipt_number or order.id}{Color.RESET} "
            f"{order.workflow_type} · {order.status.value} · "
            f"{order.updated_at.astimezone().strftime('%m-%d %H:%M')}"
        )


async def chat_loop(container: AppContainer) -> None:
    """终端对话主循环。"""
    session = container.session_manager.create()
    print(f"{Color.DIM}会话 ID：{session.id}{Color.RESET}\n")
    while True:
        try:
            raw = (await asyncio.to_thread(input, f"{Color.USER}你 ▸{Color.RESET} ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        if raw.startswith("/"):
            command = raw.split()[0].lower()
            if command in {"/quit", "/exit", "/q"}:
                break
            if command == "/help":
                print(HELP_MESSAGE)
                continue
            if command == "/new":
                session = container.session_manager.create()
                print(f"{Color.SYSTEM}已新建会话：{session.id}{Color.RESET}\n")
                continue
            if command == "/history":
                await show_history(container, session.id)
                continue
            if command == "/audit":
                await show_audit(container, session.id)
                continue
            if command == "/workorders":
                await show_workorders(container)
                continue
            print(f"{Color.SYSTEM}未知命令，输入 /help 查看帮助。{Color.RESET}")
            continue

        try:
            response = await container.chat_service.send(
                ChatRequest(session_id=session.id, message=raw)
            )
        except CampusAgentError as exc:
            print(f"{Color.ERROR}{exc.message}{Color.RESET}\n")
            continue

        print_reply(response)

        if response.requires_confirmation:
            confirmed = await handle_confirmation(container, session.id)
            if confirmed is not None:
                print_reply(confirmed)

        if response.workorder and response.workorder.status == WorkOrderStatus.COMPLETED:
            order = response.workorder
            print(
                f"{Color.BOLD}办理完成{Color.RESET} 回执：{order.receipt_number} · "
                f"预约：{order.result.get('slot_id') if order.result else ''}\n"
            )

    print(f"{Color.SYSTEM}再见。{Color.RESET}")


def main() -> int:
    """CLI 入口。"""
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from app.deps import reset_container  # 延迟导入，确保 sys.path 生效

    reset_container()
    container = build_container(get_settings())
    print_banner(container)
    try:
        asyncio.run(chat_loop(container))
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
