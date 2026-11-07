"""审计日志。

每条事件以 JSONL 追加写入 ``data/audit/audit-YYYYMMDD.jsonl``，
同时保留内存环形缓冲，支持按会话、工单查询与回放。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.config import Settings
from app.models.schema import AuditLog


def _now() -> datetime:
    """当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _jsonable(value: Any) -> Any:
    """把任意负载转换为可 JSON 序列化的结构。"""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


class AuditLogger:
    """审计日志记录器。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._directory = settings.audit_dir
        self._directory.mkdir(parents=True, exist_ok=True)
        self._memory: deque[AuditLog] = deque(maxlen=settings.audit_max_memory_records)
        self._last_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        """从最后一个带哈希的记录恢复链头；旧日志无 hash 则从空链开始。"""
        last = ""
        for log in self._iter_file_logs():
            if log.hash:
                last = log.hash
        return last

    @staticmethod
    def _digest(log: AuditLog) -> str:
        raw = log.model_dump(mode="json")
        raw.pop("hash", None)
        canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(f"{log.prev_hash}|{canonical}".encode("utf-8")).hexdigest()

    def _path(self, timestamp: datetime) -> Path:
        return self._directory / f"audit-{timestamp.strftime('%Y%m%d')}.jsonl"

    def record(
        self,
        event_type: str,
        session_id: str,
        workorder_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditLog:
        """写入一条审计事件。"""
        log = AuditLog(
            id=f"au-{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            workorder_id=workorder_id,
            event_type=event_type,
            payload=_jsonable(payload or {}),
            prev_hash=self._last_hash,
            timestamp=_now(),
        )
        log.hash = self._digest(log)
        with self._path(log.timestamp).open("a", encoding="utf-8") as handle:
            handle.write(log.model_dump_json() + "\n")
        self._last_hash = log.hash
        self._memory.append(log)
        return log

    def verify_chain(self) -> dict[str, Any]:
        """验证所有带 hash 的审计记录；旧的无 hash 记录计入 legacy。"""
        previous = ""
        checked = 0
        legacy = 0
        for log in self._iter_file_logs():
            if not log.hash:
                legacy += 1
                continue
            if log.prev_hash != previous:
                return {
                    "valid": False,
                    "checked": checked,
                    "legacy": legacy,
                    "broken_at": log.id,
                    "reason": "prev_hash_mismatch",
                }
            if self._digest(log) != log.hash:
                return {
                    "valid": False,
                    "checked": checked,
                    "legacy": legacy,
                    "broken_at": log.id,
                    "reason": "hash_mismatch",
                }
            checked += 1
            previous = log.hash
        return {
            "valid": True,
            "checked": checked,
            "legacy": legacy,
            "broken_at": None,
            "reason": "",
        }

    def _iter_file_logs(self) -> Iterable[AuditLog]:
        """按时间顺序遍历全部日志文件。"""
        for path in sorted(self._directory.glob("audit-*.jsonl")):
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            yield AuditLog.model_validate_json(line)
                        except ValueError:
                            continue
            except OSError:
                continue

    def query_session(self, session_id: str, limit: int = 500) -> list[AuditLog]:
        """按会话查询审计轨迹（时间正序）。"""
        matched = [log for log in self._iter_file_logs() if log.session_id == session_id]
        matched.sort(key=lambda item: item.timestamp)
        return matched[-limit:]

    def query_workorder(self, workorder_id: str, limit: int = 500) -> list[AuditLog]:
        """按工单查询审计轨迹。"""
        matched = [log for log in self._iter_file_logs() if log.workorder_id == workorder_id]
        matched.sort(key=lambda item: item.timestamp)
        return matched[-limit:]

    def recent(self, limit: int = 100) -> list[AuditLog]:
        """返回最近的审计事件（时间倒序）。"""
        if self._memory:
            return list(reversed(list(self._memory)))[:limit]
        logs = list(self._iter_file_logs())
        return list(reversed(logs))[:limit]

    def count(self) -> int:
        """审计事件总数。"""
        total = 0
        for _ in self._iter_file_logs():
            total += 1
        return total
