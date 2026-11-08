"""校园事务里的轻量社区数据：失物招领与意见反馈。"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.auth.models import AuthUser

CAMPUSES = ("天赐庄校区", "独墅湖校区", "阳澄湖校区", "未来校区")

SCHEMA = """
CREATE TABLE IF NOT EXISTS campus_lost_found (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    owner_college TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    campus TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '',
    place TEXT NOT NULL DEFAULT '',
    contact TEXT NOT NULL DEFAULT '',
    image_data TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campus_feedback (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    owner_college TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '其他',
    content TEXT NOT NULL,
    anonymous INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _terms(*values: str) -> list[str]:
    result: list[str] = []
    for value in values:
        if not value:
            continue
        for part in re.split(r"[\s,，、;；/|]+", value):
            part = part.strip()
            if len(part) >= 2:
                result.append(part.lower())
    return result


class CommunityStore:
    """SQLite-backed lost-and-found and feedback store."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    # ------------------------------------------------------------------
    # 失物招领
    # ------------------------------------------------------------------
    def create_lost_found(
        self,
        user: AuthUser,
        *,
        kind: str,
        campus: str,
        title: str,
        description: str = "",
        category: str = "",
        keywords: str = "",
        place: str = "",
        contact: str = "",
        image_data: str = "",
    ) -> dict[str, Any]:
        kind = "found" if kind == "found" else "lost"
        row = {
            "id": _id("lf"),
            "owner_id": user.student_id or user.username,
            "owner_name": user.name,
            "owner_college": user.college or "",
            "kind": kind,
            "campus": campus.strip(),
            "title": title.strip(),
            "description": description.strip(),
            "category": category.strip(),
            "keywords": keywords.strip(),
            "place": place.strip(),
            "contact": contact.strip(),
            "image_data": image_data.strip(),
            "status": "open",
            "created_at": _now(),
        }
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO campus_lost_found
                (id, owner_id, owner_name, owner_college, kind, campus, title,
                 description, category, keywords, place, contact, image_data, status, created_at)
                VALUES (:id, :owner_id, :owner_name, :owner_college, :kind, :campus,
                        :title, :description, :category, :keywords, :place, :contact,
                        :image_data, :status, :created_at)
                """,
                row,
            )
        return self._public_item(dict(row), user)

    def list_lost_found(
        self,
        user: AuthUser,
        *,
        campus: str = "",
        kind: str = "",
        query: str = "",
        limit: int = 60,
    ) -> dict[str, Any]:
        where = ["status = 'open'"]
        params: list[Any] = []
        if campus:
            where.append("campus = ?")
            params.append(campus)
        if kind in {"lost", "found"}:
            where.append("kind = ?")
            params.append(kind)
        if query:
            where.append("(title LIKE ? OR description LIKE ? OR keywords LIKE ? OR category LIKE ? OR place LIKE ?)")
            like = f"%{query.strip()}%"
            params.extend([like, like, like, like, like])
        sql = (
            "SELECT * FROM campus_lost_found WHERE "
            + " AND ".join(where)
            + " ORDER BY created_at DESC LIMIT ?"
        )
        params.append(max(1, min(limit, 100)))
        with self._connect() as db:
            rows = [dict(row) for row in db.execute(sql, params).fetchall()]
        items = [self._public_item(row, user) for row in rows]
        matches = self._matches_for_items(rows, user)
        return {"items": items, "matches": matches, "campuses": list(CAMPUSES)}

    def close_lost_found(self, item_id: str, user: AuthUser) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT owner_id FROM campus_lost_found WHERE id = ?", (item_id,)
            ).fetchone()
            if row is None:
                return False
            owner = user.student_id or user.username
            if row["owner_id"] != owner and user.role not in {"admin", "auditor"}:
                return False
            db.execute(
                "UPDATE campus_lost_found SET status = 'closed' WHERE id = ?",
                (item_id,),
            )
        return True

    def _public_item(self, row: dict[str, Any], user: AuthUser) -> dict[str, Any]:
        image = row.get("image_data") or ""
        return {
            "id": row["id"],
            "kind": row["kind"],
            "campus": row["campus"],
            "title": row["title"],
            "description": row["description"],
            "category": row["category"],
            "keywords": row["keywords"],
            "place": row["place"],
            "contact": row["contact"],
            "image_url": image if image.startswith("data:image/") else "",
            "status": row["status"],
            "created_at": row["created_at"],
            "is_mine": (row["owner_id"] == (user.student_id or user.username)),
        }

    def _matches_for_items(
        self, rows: list[dict[str, Any]], user: AuthUser
    ) -> list[dict[str, Any]]:
        if not rows:
            return []
        campuses = {row["campus"] for row in rows}
        with self._connect() as db:
            placeholders = ",".join("?" for _ in campuses)
            others = [
                dict(row)
                for row in db.execute(
                    f"SELECT * FROM campus_lost_found WHERE status = 'open' "
                    f"AND campus IN ({placeholders})",
                    list(campuses),
                ).fetchall()
            ]
        result: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for left in rows:
            for right in others:
                if left["id"] == right["id"] or left["kind"] == right["kind"]:
                    continue
                pair = tuple(sorted((left["id"], right["id"])))
                if pair in seen:
                    continue
                score, reasons = self._match_score(left, right)
                if score <= 0:
                    continue
                seen.add(pair)
                result.append(
                    {
                        "score": score,
                        "reasons": reasons,
                        "lost": self._public_item(
                            left if left["kind"] == "lost" else right, user
                        ),
                        "found": self._public_item(
                            right if right["kind"] == "found" else left, user
                        ),
                    }
                )
        result.sort(key=lambda item: item["score"], reverse=True)
        return result[:12]

    @staticmethod
    def _match_score(left: dict[str, Any], right: dict[str, Any]) -> tuple[int, list[str]]:
        left_terms = _terms(
            left.get("keywords", ""),
            left.get("title", ""),
            left.get("category", ""),
            left.get("description", ""),
        )
        right_text = " ".join(
            str(right.get(key, ""))
            for key in ("title", "category", "keywords", "description", "place")
        ).lower()
        score = 0
        reasons: list[str] = []
        for term in left_terms:
            if term and term in right_text:
                score += 2
                reasons.append(term)
        # 对没有空格的中文描述补一层二字片段匹配。
        left_text = " ".join(
            str(left.get(key, ""))
            for key in ("title", "category", "keywords", "description", "place")
        )
        for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", left_text):
            for index in range(0, max(1, len(chunk) - 1)):
                gram = chunk[index : index + 2]
                if gram and gram in right_text and gram not in reasons:
                    score += 1
                    reasons.append(gram)
        return score, reasons[:4]

    # ------------------------------------------------------------------
    # 意见反馈
    # ------------------------------------------------------------------
    def create_feedback(
        self,
        user: AuthUser,
        *,
        category: str,
        content: str,
        anonymous: bool = False,
    ) -> dict[str, Any]:
        row = {
            "id": _id("fb"),
            "owner_id": user.student_id or user.username,
            "owner_name": user.name,
            "owner_college": user.college or "",
            "category": category.strip() or "其他",
            "content": content.strip(),
            "anonymous": 1 if anonymous else 0,
            "status": "open",
            "created_at": _now(),
        }
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO campus_feedback
                (id, owner_id, owner_name, owner_college, category, content,
                 anonymous, status, created_at)
                VALUES (:id, :owner_id, :owner_name, :owner_college, :category,
                        :content, :anonymous, :status, :created_at)
                """,
                row,
            )
        return self._public_feedback(row, user)

    def list_feedback(self, user: AuthUser, *, category: str = "") -> dict[str, Any]:
        staff = user.role in {"counselor", "auditor", "admin"}
        params: list[Any] = []
        if staff:
            where = "1=1"
            if user.role == "counselor" and user.college:
                where = "owner_college = ?"
                params.append(user.college)
        else:
            where = "owner_id = ?"
            params.append(user.student_id or user.username)
        if category:
            where += " AND category = ?"
            params.append(category)
        with self._connect() as db:
            rows = [
                dict(row)
                for row in db.execute(
                    f"SELECT * FROM campus_feedback WHERE {where} ORDER BY created_at DESC LIMIT 100",
                    params,
                ).fetchall()
            ]
        return {
            "items": [self._public_feedback(row, user) for row in rows],
            "staff_view": staff,
        }

    def _public_feedback(self, row: dict[str, Any], user: AuthUser) -> dict[str, Any]:
        staff = user.role in {"counselor", "auditor", "admin"}
        hidden = bool(row.get("anonymous")) and staff
        return {
            "id": row["id"],
            "category": row["category"],
            "content": row["content"],
            "anonymous": bool(row["anonymous"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "owner_name": "匿名学生" if hidden else row["owner_name"],
            "owner_college": "" if hidden else row["owner_college"],
            "is_mine": row["owner_id"] == (user.student_id or user.username),
            "staff_view": staff,
        }
