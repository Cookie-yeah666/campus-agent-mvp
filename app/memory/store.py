"""JSON 文件存储。

会话与工单按 ID 分文件存放，写入采用临时文件替换，
避免进程中断导致半截 JSON。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import Settings
from app.core.enums import WorkOrderStatus
from app.core.exceptions import SessionNotFoundError, WorkOrderNotFoundError
from app.models.schema import ChatSession, WorkOrder


def _atomic_write(path: Path, payload: str) -> None:
    """原子写入文本文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


class SessionStore:
    """会话存储：内存索引 + JSON 落盘。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._directory = settings.sessions_dir
        self._directory.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, ChatSession] = {}
        self._load()

    def _load(self) -> None:
        """启动时恢复全部会话。"""
        for path in sorted(self._directory.glob("*.json")):
            try:
                session = ChatSession.model_validate_json(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            self._sessions[session.id] = session

    def _path(self, session_id: str) -> Path:
        return self._directory / f"{session_id}.json"

    def save(self, session: ChatSession) -> None:
        """保存会话。"""
        self._sessions[session.id] = session
        _atomic_write(self._path(session.id), session.model_dump_json(indent=2))

    def get(self, session_id: str) -> ChatSession:
        """获取会话。

        Raises:
            SessionNotFoundError: 会话不存在。
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"会话 {session_id} 不存在")
        return session

    def exists(self, session_id: str) -> bool:
        """判断会话是否存在。"""
        return session_id in self._sessions

    def list(self) -> list[ChatSession]:
        """按更新时间倒序返回全部会话。"""
        return sorted(self._sessions.values(), key=lambda item: item.updated_at, reverse=True)

    def delete(self, session_id: str) -> None:
        """删除会话。"""
        if session_id not in self._sessions:
            raise SessionNotFoundError(f"会话 {session_id} 不存在")
        self._sessions.pop(session_id)
        path = self._path(session_id)
        if path.exists():
            path.unlink()

    def count(self) -> int:
        """会话总数。"""
        return len(self._sessions)


class WorkOrderStore:
    """工单存储。"""

    def __init__(self, settings: Settings) -> None:
        self._directory = settings.workorders_dir
        self._directory.mkdir(parents=True, exist_ok=True)
        self._orders: dict[str, WorkOrder] = {}
        self._load()

    def _load(self) -> None:
        """启动时恢复全部工单。"""
        for path in sorted(self._directory.glob("*.json")):
            try:
                order = WorkOrder.model_validate_json(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            self._orders[order.id] = order

    def _path(self, workorder_id: str) -> Path:
        return self._directory / f"{workorder_id}.json"

    def save(self, workorder: WorkOrder) -> None:
        """保存工单。"""
        self._orders[workorder.id] = workorder
        _atomic_write(self._path(workorder.id), workorder.model_dump_json(indent=2))

    def get(self, workorder_id: str) -> WorkOrder:
        """获取工单。

        Raises:
            WorkOrderNotFoundError: 工单不存在。
        """
        order = self._orders.get(workorder_id)
        if order is None:
            raise WorkOrderNotFoundError(f"工单 {workorder_id} 不存在")
        return order

    def list(self, status: WorkOrderStatus | None = None) -> list[WorkOrder]:
        """按更新时间倒序返回工单，可按状态过滤。"""
        orders = list(self._orders.values())
        if status is not None:
            orders = [order for order in orders if order.status == status]
        return sorted(orders, key=lambda item: item.updated_at, reverse=True)

    def counts(self) -> dict[str, int]:
        """按状态统计工单数。"""
        result: dict[str, int] = {}
        for order in self._orders.values():
            key = order.status.value
            result[key] = result.get(key, 0) + 1
        return result

    def delete(self, workorder_id: str) -> None:
        """删除工单。"""
        self._orders.pop(workorder_id, None)
        path = self._path(workorder_id)
        if path.exists():
            path.unlink()

    def count(self) -> int:
        """工单总数。"""
        return len(self._orders)

    def dump(self) -> list[dict[str, Any]]:
        """导出全部工单（调试用）。"""
        return [json.loads(order.model_dump_json()) for order in self.list()]
