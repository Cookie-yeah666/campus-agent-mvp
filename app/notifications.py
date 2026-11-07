"""站内通知：工单转人工、办结等事件。

课程原型用单个 JSON 文件；生产应换消息队列/推送服务。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class NotificationStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self._items = list(payload.get("items", []))
        except (json.JSONDecodeError, OSError):
            self._items = []

    def _save(self) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"items": self._items[-500:]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def add(
        self,
        owner_id: str,
        *,
        title: str,
        message: str,
        link: str = "",
        dedupe_key: str = "",
    ) -> dict[str, Any] | None:
        if not owner_id:
            return None
        if dedupe_key and any(
            item.get("owner_id") == owner_id and item.get("dedupe_key") == dedupe_key
            for item in self._items
        ):
            return None
        item = {
            "id": f"nt-{uuid.uuid4().hex[:10]}",
            "owner_id": owner_id,
            "title": title,
            "message": message,
            "link": link,
            "dedupe_key": dedupe_key,
            "read": False,
            "created_at": _now(),
        }
        self._items.append(item)
        self._save()
        return item

    def list(self, owner_id: str, limit: int = 20) -> list[dict[str, Any]]:
        items = [item for item in self._items if item.get("owner_id") == owner_id]
        return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)[:limit]

    def unread_count(self, owner_id: str) -> int:
        return sum(1 for item in self._items if item.get("owner_id") == owner_id and not item.get("read"))

    def mark_read(self, owner_id: str, notification_id: str | None = None) -> int:
        changed = 0
        for item in self._items:
            if item.get("owner_id") != owner_id:
                continue
            if notification_id and item.get("id") != notification_id:
                continue
            if not item.get("read"):
                item["read"] = True
                changed += 1
        if changed:
            self._save()
        return changed
