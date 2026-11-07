"""可持久化的学生名册。

设计目标：
- 与可重置的 ``data/`` 演示数据分离，学生名册放在 ``registry/``；
- 以 ``(届, 学院, 学号)`` 为业务唯一键，支持多个学院、多个年级；
- 保留导入批次与原始文件信息，便于追责与重复导入；
- 原始手机号只落库，API 默认脱敏返回。
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

STATUS_LABELS: dict[str, str] = {
    "active": "在籍",
    "missing_id": "待补学号",
    "retained": "保留资格",
    "retaking": "复读",
    "not_arrived": "未报到",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_batches (
    batch_id TEXT PRIMARY KEY,
    imported_at TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_sha256 TEXT,
    college TEXT NOT NULL,
    cohort TEXT NOT NULL,
    total_rows INTEGER NOT NULL DEFAULT 0,
    inserted INTEGER NOT NULL DEFAULT 0,
    updated INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    issues INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS students (
    record_key TEXT PRIMARY KEY,
    student_id TEXT,
    cohort TEXT NOT NULL,
    college TEXT NOT NULL,
    major TEXT NOT NULL DEFAULT '',
    class_name TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    phone TEXT,
    gender TEXT,
    dorm_building TEXT,
    dorm_room TEXT,
    campus TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT,
    source_file TEXT,
    source_row INTEGER,
    import_batch_id TEXT,
    imported_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_students_identity
    ON students(cohort, college, student_id)
    WHERE student_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_students_college ON students(college);
CREATE INDEX IF NOT EXISTS ix_students_cohort ON students(cohort);
CREATE INDEX IF NOT EXISTS ix_students_class ON students(class_name);
CREATE INDEX IF NOT EXISTS ix_students_name ON students(name);
"""

_ID_RE = re.compile(r"^\d{10}$")


def utc_now() -> str:
    """UTC ISO 时间字符串。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_student_id(value: Any) -> str | None:
    """把 Excel/CSV 中的学号统一成 10 位字符串。"""
    if value is None:
        return None
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    text = re.sub(r"\s+", "", text)
    return text if _ID_RE.fullmatch(text) else None


def mask_phone(phone: str | None) -> str | None:
    """手机号脱敏：138****1234。"""
    if not phone:
        return None
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 11:
        return f"{digits[:3]}****{digits[-4:]}"
    return None


class StudentRegistry:
    """学生名册的 SQLite 数据访问层。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    # ------------------------------------------------------------------ 连接
    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            connection.execute(
                "INSERT OR IGNORE INTO schema_meta(key, value) VALUES('schema_version', '1')"
            )

    # ------------------------------------------------------------------ 查询
    def lookup(
        self,
        student_id: str,
        *,
        cohort: str | None = None,
        college: str | None = None,
    ) -> dict[str, Any] | None:
        """按学号查询，默认返回最近导入的一条。"""
        clauses = ["student_id = ?"]
        params: list[Any] = [student_id]
        if cohort:
            clauses.append("cohort = ?")
            params.append(cohort)
        if college:
            clauses.append("college = ?")
            params.append(college)
        sql = (
            "SELECT * FROM students WHERE "
            + " AND ".join(clauses)
            + " ORDER BY updated_at DESC LIMIT 1"
        )
        with self._connect() as connection:
            row = connection.execute(sql, params).fetchone()
        return dict(row) if row else None

    def search(
        self,
        *,
        college: str | None = None,
        cohort: str | None = None,
        major: str | None = None,
        class_name: str | None = None,
        status: str | None = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """分页检索，返回 ``(items, total)``。"""
        clauses: list[str] = ["1 = 1"]
        params: list[Any] = []
        for field, value in (
            ("college", college),
            ("cohort", cohort),
            ("major", major),
            ("class_name", class_name),
            ("status", status),
        ):
            if value:
                clauses.append(f"{field} = ?")
                params.append(value)
        if query:
            like = f"%{query.strip()}%"
            clauses.append(
                "(student_id LIKE ? OR name LIKE ? OR class_name LIKE ? OR major LIKE ?)"
            )
            params.extend([like, like, like, like])
        where = " AND ".join(clauses)
        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM students WHERE {where}", params
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT * FROM students
                WHERE {where}
                ORDER BY college, cohort DESC, class_name, student_id
                LIMIT ? OFFSET ?
                """,
                [*params, max(1, min(limit, 200)), max(0, offset)],
            ).fetchall()
        return [dict(row) for row in rows], int(total)

    def stats(self) -> dict[str, Any]:
        """名册统计与筛选选项。"""
        with self._connect() as connection:
            total = connection.execute("SELECT COUNT(*) FROM students").fetchone()[0]
            issues = connection.execute(
                "SELECT COUNT(*) FROM students WHERE status != 'active'"
            ).fetchone()[0]
            colleges = connection.execute(
                "SELECT COUNT(DISTINCT college) FROM students"
            ).fetchone()[0]
            cohorts = connection.execute(
                "SELECT COUNT(DISTINCT cohort) FROM students"
            ).fetchone()[0]
            classes = connection.execute(
                "SELECT COUNT(DISTINCT class_name) FROM students WHERE class_name != ''"
            ).fetchone()[0]
            majors = connection.execute(
                "SELECT COUNT(DISTINCT major) FROM students WHERE major != ''"
            ).fetchone()[0]
            by_college = connection.execute(
                "SELECT college AS name, COUNT(*) AS count FROM students GROUP BY college ORDER BY count DESC"
            ).fetchall()
            by_cohort = connection.execute(
                "SELECT cohort AS name, COUNT(*) AS count FROM students GROUP BY cohort ORDER BY cohort DESC"
            ).fetchall()
            by_major = connection.execute(
                "SELECT major AS name, COUNT(*) AS count FROM students WHERE major != '' GROUP BY major ORDER BY count DESC"
            ).fetchall()
            by_status = connection.execute(
                "SELECT status AS name, COUNT(*) AS count FROM students GROUP BY status ORDER BY count DESC"
            ).fetchall()
            latest = connection.execute(
                "SELECT * FROM import_batches ORDER BY imported_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
        return {
            "total": int(total),
            "issues": int(issues),
            "colleges": int(colleges),
            "cohorts": int(cohorts),
            "classes": int(classes),
            "majors": int(majors),
            "by_college": [dict(row) for row in by_college],
            "by_cohort": [dict(row) for row in by_cohort],
            "by_major": [dict(row) for row in by_major],
            "by_status": [
                {
                    "name": row["name"],
                    "label": STATUS_LABELS.get(row["name"], row["name"]),
                    "count": row["count"],
                }
                for row in by_status
            ],
            "latest_batch": self._batch_dict(latest) if latest else None,
        }

    def imports(self, limit: int = 10) -> list[dict[str, Any]]:
        """最近导入批次。"""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM import_batches ORDER BY imported_at DESC, rowid DESC LIMIT ?",
                (max(1, min(limit, 50)),),
            ).fetchall()
        return [self._batch_dict(row) for row in rows]

    # ------------------------------------------------------------------ 写入
    def clear_scope(self, college: str, cohort: str) -> int:
        """清空某学院某届，返回删除行数。"""
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM students WHERE college = ? AND cohort = ?", (college, cohort)
            )
            return int(cursor.rowcount)

    def upsert_batch(
        self,
        rows: Iterable[dict[str, Any]],
        *,
        source_file: str,
        source_sha256: str | None,
        college: str,
        cohort: str,
        batch_id: str | None = None,
    ) -> dict[str, Any]:
        """批量 upsert，并记录导入批次。

        rows 中每行字段：student_id, name, major, class_name, phone, gender,
        dorm_building, dorm_room, campus, status, notes, source_row。
        """
        batch_id = batch_id or f"IMP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
        now = utc_now()
        inserted = updated = skipped = issues = 0
        errors: list[dict[str, Any]] = []
        with self._connect() as connection:
            for row in rows:
                student_id = normalize_student_id(row.get("student_id"))
                name = str(row.get("name") or "").strip()
                class_name = str(row.get("class_name") or "").strip()
                if not name or not class_name:
                    skipped += 1
                    issues += 1
                    errors.append(
                        {
                            "row": row.get("source_row"),
                            "reason": "姓名或班级为空",
                            "name": name,
                        }
                    )
                    continue
                record_key = self._record_key(
                    cohort=cohort,
                    college=college,
                    student_id=student_id,
                    name=name,
                    class_name=class_name,
                    source_row=row.get("source_row"),
                )
                existing = connection.execute(
                    "SELECT 1 FROM students WHERE record_key = ?", (record_key,)
                ).fetchone()
                status = str(row.get("status") or ("active" if student_id else "missing_id"))
                if status not in STATUS_LABELS:
                    status = "active" if student_id else "missing_id"
                if status != "active":
                    issues += 1
                connection.execute(
                    """
                    INSERT INTO students (
                        record_key, student_id, cohort, college, major, class_name,
                        name, phone, gender, dorm_building, dorm_room, campus,
                        status, notes, source_file, source_row, import_batch_id,
                        imported_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(record_key) DO UPDATE SET
                        student_id = excluded.student_id,
                        cohort = excluded.cohort,
                        college = excluded.college,
                        major = excluded.major,
                        class_name = excluded.class_name,
                        name = excluded.name,
                        phone = excluded.phone,
                        gender = excluded.gender,
                        dorm_building = excluded.dorm_building,
                        dorm_room = excluded.dorm_room,
                        campus = excluded.campus,
                        status = excluded.status,
                        notes = excluded.notes,
                        source_file = excluded.source_file,
                        source_row = excluded.source_row,
                        import_batch_id = excluded.import_batch_id,
                        updated_at = excluded.updated_at
                    """,
                    (
                        record_key,
                        student_id,
                        cohort,
                        college,
                        str(row.get("major") or "").strip(),
                        class_name,
                        name,
                        row.get("phone"),
                        row.get("gender"),
                        row.get("dorm_building"),
                        row.get("dorm_room"),
                        row.get("campus"),
                        status,
                        row.get("notes"),
                        source_file,
                        row.get("source_row"),
                        batch_id,
                        now,
                        now,
                    ),
                )
                if existing:
                    updated += 1
                else:
                    inserted += 1
            connection.execute(
                """
                INSERT INTO import_batches (
                    batch_id, imported_at, source_file, source_sha256, college, cohort,
                    total_rows, inserted, updated, skipped, issues, errors_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    now,
                    source_file,
                    source_sha256,
                    college,
                    cohort,
                    inserted + updated + skipped,
                    inserted,
                    updated,
                    skipped,
                    issues,
                    json.dumps(errors, ensure_ascii=False),
                ),
            )
        return {
            "batch_id": batch_id,
            "imported_at": now,
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "issues": issues,
            "total_rows": inserted + updated + skipped,
            "errors": errors[:20],
        }

    # ------------------------------------------------------------------ 输出
    def public_student(self, row: dict[str, Any]) -> dict[str, Any]:
        """转成 API/前端可用的脱敏结构。"""
        dorm_parts = [row.get("dorm_building"), row.get("dorm_room")]
        dorm = "-".join(str(part) for part in dorm_parts if part)
        return {
            "student_id": row.get("student_id"),
            "name": row.get("name"),
            "cohort": row.get("cohort"),
            "college": row.get("college"),
            "major": row.get("major"),
            "class_name": row.get("class_name"),
            "campus": row.get("campus"),
            "dorm": dorm or None,
            "gender": row.get("gender"),
            "status": row.get("status"),
            "status_label": STATUS_LABELS.get(row.get("status", ""), row.get("status")),
            "phone_masked": mask_phone(row.get("phone")),
            "source": "roster",
        }

    @staticmethod
    def _record_key(
        *,
        cohort: str,
        college: str,
        student_id: str | None,
        name: str,
        class_name: str,
        source_row: Any,
    ) -> str:
        if student_id:
            return f"{cohort}|{college}|{student_id}"
        return f"{cohort}|{college}|row:{source_row}|{name}|{class_name}"

    @staticmethod
    def _batch_dict(row: sqlite3.Row) -> dict[str, Any]:
        payload = dict(row)
        try:
            payload["errors"] = json.loads(payload.pop("errors_json", "[]"))
        except json.JSONDecodeError:
            payload["errors"] = []
        return payload
