"""幂等键管理。

键格式：``{workflow_type}:{student_id}:{date}``，也可由客户端显式传入。
映射持久化到 JSON，重启后仍然生效。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import Settings


class IdempotencyStore:
    """幂等键 -> 工单 ID 映射。"""

    def __init__(self, settings: Settings) -> None:
        self._path: Path = settings.idempotency_path
        self._mapping: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        """从磁盘恢复映射。"""
        if not self._path.exists():
            return
        try:
            payload: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._mapping = {
            str(key): str(value) for key, value in payload.items() if isinstance(value, str)
        }

    def _save(self) -> None:
        """原子写入映射文件。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._mapping, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self._path)

    def get(self, key: str) -> str | None:
        """查询幂等键对应的工单 ID。"""
        return self._mapping.get(key)

    def set(self, key: str, workorder_id: str) -> None:
        """登记幂等键。"""
        self._mapping[key] = workorder_id
        self._save()

    def delete(self, key: str) -> None:
        """删除幂等键。"""
        if key in self._mapping:
            self._mapping.pop(key)
            self._save()

    def all(self) -> dict[str, str]:
        """返回全部映射（只读副本）。"""
        return dict(self._mapping)
