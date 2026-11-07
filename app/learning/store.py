"""学习空间 SQLite 存储。

与办事会话/工单分开，避免学生个人学习数据进入可重置的演示数据。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class LearningStore:
    """轻量 SQLite 存储；每个方法独立连接，适合单进程课程原型。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS learning_libraries (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    subject TEXT NOT NULL DEFAULT '',
                    deleted_at TEXT,
                    purge_at TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_learning_libraries_owner
                    ON learning_libraries(owner_id);

                CREATE TABLE IF NOT EXISTS learning_questions (
                    id TEXT PRIMARY KEY,
                    library_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    image_path TEXT,
                    question_text TEXT NOT NULL,
                    options_json TEXT NOT NULL DEFAULT '[]',
                    reference_answer TEXT NOT NULL DEFAULT '',
                    analysis TEXT NOT NULL DEFAULT '',
                    knowledge_points TEXT NOT NULL DEFAULT '',
                    difficulty TEXT NOT NULL DEFAULT '中等',
                    review_due TEXT NOT NULL DEFAULT '',
                    review_streak INTEGER NOT NULL DEFAULT 0,
                    last_reviewed_at TEXT,
                    deleted_at TEXT,
                    purge_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(library_id) REFERENCES learning_libraries(id)
                );
                CREATE INDEX IF NOT EXISTS idx_learning_questions_library
                    ON learning_questions(library_id, owner_id);

                CREATE TABLE IF NOT EXISTS learning_attempts (
                    id TEXT PRIMARY KEY,
                    question_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    answer_text TEXT NOT NULL,
                    correctness TEXT NOT NULL DEFAULT 'partial',
                    score REAL NOT NULL DEFAULT 0,
                    feedback_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(question_id) REFERENCES learning_questions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_learning_attempts_question
                    ON learning_attempts(question_id, owner_id);

                CREATE TABLE IF NOT EXISTS learning_tasks (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    duration_min INTEGER NOT NULL DEFAULT 60,
                    priority TEXT NOT NULL DEFAULT 'none',
                    start_date TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    remind_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    actual_min INTEGER NOT NULL DEFAULT 0,
                    source_exam_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_learning_tasks_owner
                    ON learning_tasks(owner_id, status, due_date);

                CREATE TABLE IF NOT EXISTS learning_exams (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    course_name TEXT NOT NULL,
                    exam_date TEXT NOT NULL,
                    start_time TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_learning_exams_owner
                    ON learning_exams(owner_id, exam_date);

                CREATE TABLE IF NOT EXISTS learning_focus (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    task_id TEXT,
                    mode TEXT NOT NULL DEFAULT 'pomodoro',
                    planned_min INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    actual_min INTEGER,
                    completed INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_learning_focus_owner
                    ON learning_focus(owner_id, started_at);

                CREATE TABLE IF NOT EXISTS learning_course_materials (
                    id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_learning_materials_course
                    ON learning_course_materials(owner_id, course_id, created_at);

                CREATE TABLE IF NOT EXISTS learning_vision_profiles (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT 'custom',
                    model TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    official_url TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    key_cipher TEXT NOT NULL,
                    key_mask TEXT NOT NULL,
                    key_fingerprint TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'unknown',
                    last_tested_at TEXT,
                    last_test_message TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_learning_vision_profiles_owner
                    ON learning_vision_profiles(owner_id, is_active);

                CREATE TABLE IF NOT EXISTS learning_vision_settings (
                    owner_id TEXT PRIMARY KEY,
                    base_url TEXT NOT NULL,
                    model TEXT NOT NULL,
                    api_key_cipher TEXT NOT NULL,
                    key_mask TEXT NOT NULL,
                    key_fingerprint TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS learning_courses (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    teacher TEXT NOT NULL DEFAULT '',
                    weekday INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    location TEXT NOT NULL DEFAULT '',
                    weeks TEXT NOT NULL DEFAULT '',
                    week_parity TEXT NOT NULL DEFAULT 'all',
                    assignment TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_learning_courses_owner
                    ON learning_courses(owner_id, weekday);

                CREATE TABLE IF NOT EXISTS learning_calendar_settings (
                    owner_id TEXT PRIMARY KEY,
                    semester_start TEXT NOT NULL DEFAULT ''
                );
                """
            )
            columns = [
                row[1]
                for row in db.execute(
                    "PRAGMA table_info(learning_vision_settings)"
                ).fetchall()
            ]
            if "key_fingerprint" not in columns:
                db.execute(
                    "ALTER TABLE learning_vision_settings "
                    "ADD COLUMN key_fingerprint TEXT NOT NULL DEFAULT ''"
                )
            library_columns = [
                row[1]
                for row in db.execute("PRAGMA table_info(learning_libraries)").fetchall()
            ]
            for column in ("deleted_at", "purge_at"):
                if column not in library_columns:
                    db.execute(f"ALTER TABLE learning_libraries ADD COLUMN {column} TEXT")
            course_columns = [
                row[1]
                for row in db.execute("PRAGMA table_info(learning_courses)").fetchall()
            ]
            if "week_parity" not in course_columns:
                db.execute(
                    "ALTER TABLE learning_courses "
                    "ADD COLUMN week_parity TEXT NOT NULL DEFAULT 'all'"
                )
            task_columns = [
                row[1] for row in db.execute("PRAGMA table_info(learning_tasks)").fetchall()
            ]
            if "source_exam_id" not in task_columns:
                db.execute(
                    "ALTER TABLE learning_tasks "
                    "ADD COLUMN source_exam_id TEXT NOT NULL DEFAULT ''"
                )
            question_columns = [
                row[1]
                for row in db.execute("PRAGMA table_info(learning_questions)").fetchall()
            ]
            for column, ddl in (
                ("review_due", "TEXT NOT NULL DEFAULT ''"),
                ("review_streak", "INTEGER NOT NULL DEFAULT 0"),
                ("last_reviewed_at", "TEXT"),
                ("deleted_at", "TEXT"),
                ("purge_at", "TEXT"),
            ):
                if column not in question_columns:
                    db.execute(
                        f"ALTER TABLE learning_questions ADD COLUMN {column} {ddl}"
                    )
            existing_profiles = db.execute(
                "SELECT COUNT(*) AS count FROM learning_vision_profiles"
            ).fetchone()["count"]
            if existing_profiles == 0:
                old_rows = db.execute(
                    "SELECT * FROM learning_vision_settings"
                ).fetchall()
                for row in old_rows:
                    db.execute(
                        """
                        INSERT INTO learning_vision_profiles
                            (id, owner_id, name, provider, model, base_url,
                             official_url, note, key_cipher, key_mask,
                             key_fingerprint, status, last_tested_at,
                             last_test_message, is_active, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            _id("prof"),
                            row["owner_id"],
                            "默认配置",
                            "custom",
                            row["model"],
                            row["base_url"],
                            "",
                            "",
                            row["api_key_cipher"],
                            row["key_mask"],
                            row["key_fingerprint"],
                            "unknown",
                            None,
                            "",
                            1,
                            _now(),
                        ),
                    )

    # ------------------------------------------------------------------
    # 错题本
    # ------------------------------------------------------------------
    def create_library(self, owner_id: str, name: str, subject: str = "") -> dict[str, Any]:
        row = {
            "id": _id("lib"),
            "owner_id": owner_id,
            "name": name.strip(),
            "subject": subject.strip(),
            "created_at": _now(),
        }
        with self._connect() as db:
            db.execute(
                "INSERT INTO learning_libraries (id, owner_id, name, subject, created_at) "
                "VALUES (:id, :owner_id, :name, :subject, :created_at)",
                row,
            )
        return row

    def list_libraries(self, owner_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT l.*, COUNT(q.id) AS question_count
                FROM learning_libraries l
                LEFT JOIN learning_questions q ON q.library_id = l.id
                    AND q.deleted_at IS NULL
                WHERE l.owner_id = ? AND l.deleted_at IS NULL
                GROUP BY l.id
                ORDER BY l.created_at DESC
                """,
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_library(self, library_id: str, owner_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return _row(
                db.execute(
                    "SELECT * FROM learning_libraries WHERE id = ? AND owner_id = ? "
                    "AND deleted_at IS NULL",
                    (library_id, owner_id),
                ).fetchone()
            )

    def soft_delete_library(self, library_id: str, owner_id: str) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        purge_at = (now + timedelta(days=7)).isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                "UPDATE learning_libraries SET deleted_at = ?, purge_at = ? "
                "WHERE id = ? AND owner_id = ? AND deleted_at IS NULL",
                (now.isoformat(timespec="seconds"), purge_at, library_id, owner_id),
            )
            row = db.execute(
                "SELECT * FROM learning_libraries WHERE id = ? AND owner_id = ?",
                (library_id, owner_id),
            ).fetchone()
        return _row(row)

    def list_trash_libraries(self, owner_id: str) -> list[dict[str, Any]]:
        self.purge_expired_libraries(owner_id)
        with self._connect() as db:
            rows = db.execute(
                "SELECT l.*, COUNT(q.id) AS question_count "
                "FROM learning_libraries l "
                "LEFT JOIN learning_questions q ON q.library_id = l.id "
                "WHERE l.owner_id = ? AND l.deleted_at IS NOT NULL "
                "GROUP BY l.id ORDER BY l.deleted_at DESC",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def restore_library(self, library_id: str, owner_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            db.execute(
                "UPDATE learning_libraries SET deleted_at = NULL, purge_at = NULL "
                "WHERE id = ? AND owner_id = ? AND deleted_at IS NOT NULL",
                (library_id, owner_id),
            )
            row = db.execute(
                "SELECT * FROM learning_libraries WHERE id = ? AND owner_id = ?",
                (library_id, owner_id),
            ).fetchone()
        return _row(row)

    def purge_library(self, library_id: str, owner_id: str) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM learning_libraries WHERE id = ? AND owner_id = ? "
                "AND deleted_at IS NOT NULL",
                (library_id, owner_id),
            ).fetchone()
            if row is None:
                return False
            ids = [
                item["id"]
                for item in db.execute(
                    "SELECT id FROM learning_questions WHERE library_id = ? AND owner_id = ?",
                    (library_id, owner_id),
                ).fetchall()
            ]
            for question_id in ids:
                db.execute(
                    "DELETE FROM learning_attempts WHERE question_id = ? AND owner_id = ?",
                    (question_id, owner_id),
                )
            db.execute(
                "DELETE FROM learning_questions WHERE library_id = ? AND owner_id = ?",
                (library_id, owner_id),
            )
            cursor = db.execute(
                "DELETE FROM learning_libraries WHERE id = ? AND owner_id = ?",
                (library_id, owner_id),
            )
        return cursor.rowcount > 0

    def purge_expired_libraries(self, owner_id: str | None = None) -> int:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as db:
            params: list[Any] = [now]
            where = "deleted_at IS NOT NULL AND purge_at IS NOT NULL AND purge_at <= ?"
            if owner_id:
                where += " AND owner_id = ?"
                params.append(owner_id)
            rows = db.execute(
                f"SELECT id, owner_id FROM learning_libraries WHERE {where}", params
            ).fetchall()
        purged = 0
        for row in rows:
            if self.purge_library(row["id"], row["owner_id"]):
                purged += 1
        return purged

    def delete_library(self, library_id: str, owner_id: str) -> bool:
        with self._connect() as db:
            ids = [
                row["id"]
                for row in db.execute(
                    "SELECT id FROM learning_questions WHERE library_id = ? AND owner_id = ?",
                    (library_id, owner_id),
                ).fetchall()
            ]
            for question_id in ids:
                db.execute(
                    "DELETE FROM learning_attempts WHERE question_id = ? AND owner_id = ?",
                    (question_id, owner_id),
                )
            db.execute(
                "DELETE FROM learning_questions WHERE library_id = ? AND owner_id = ?",
                (library_id, owner_id),
            )
            cursor = db.execute(
                "DELETE FROM learning_libraries WHERE id = ? AND owner_id = ?",
                (library_id, owner_id),
            )
            return cursor.rowcount > 0

    def create_question(
        self,
        *,
        library_id: str,
        owner_id: str,
        question_text: str,
        image_path: str | None,
        options: list[str],
        reference_answer: str,
        analysis: str,
        knowledge_points: str,
        difficulty: str,
    ) -> dict[str, Any]:
        row = {
            "id": _id("q"),
            "library_id": library_id,
            "owner_id": owner_id,
            "image_path": image_path,
            "question_text": question_text.strip(),
            "options_json": json.dumps(options, ensure_ascii=False),
            "reference_answer": reference_answer.strip(),
            "analysis": analysis.strip(),
            "knowledge_points": knowledge_points.strip(),
            "difficulty": difficulty.strip(),
            "created_at": _now(),
        }
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO learning_questions
                    (id, library_id, owner_id, image_path, question_text, options_json,
                     reference_answer, analysis, knowledge_points, difficulty, created_at)
                VALUES
                    (:id, :library_id, :owner_id, :image_path, :question_text, :options_json,
                     :reference_answer, :analysis, :knowledge_points, :difficulty, :created_at)
                """,
                row,
            )
        return row

    def list_questions(self, owner_id: str, library_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM learning_questions WHERE owner_id = ? AND library_id = ? "
                "AND deleted_at IS NULL ORDER BY created_at DESC",
                (owner_id, library_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_question(self, question_id: str, owner_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return _row(
                db.execute(
                    "SELECT * FROM learning_questions WHERE id = ? AND owner_id = ? "
                    "AND deleted_at IS NULL",
                    (question_id, owner_id),
                ).fetchone()
            )

    def soft_delete_question(self, question_id: str, owner_id: str) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        purge_at = (now + timedelta(days=7)).isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                "UPDATE learning_questions SET deleted_at = ?, purge_at = ? "
                "WHERE id = ? AND owner_id = ? AND deleted_at IS NULL",
                (now.isoformat(timespec="seconds"), purge_at, question_id, owner_id),
            )
            row = db.execute(
                "SELECT * FROM learning_questions WHERE id = ? AND owner_id = ?",
                (question_id, owner_id),
            ).fetchone()
        return _row(row)

    def list_trash_questions(self, owner_id: str) -> list[dict[str, Any]]:
        self.purge_expired_questions(owner_id)
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM learning_questions WHERE owner_id = ? "
                "AND deleted_at IS NOT NULL ORDER BY deleted_at DESC",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def restore_question(self, question_id: str, owner_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            db.execute(
                "UPDATE learning_questions SET deleted_at = NULL, purge_at = NULL "
                "WHERE id = ? AND owner_id = ? AND deleted_at IS NOT NULL",
                (question_id, owner_id),
            )
            row = db.execute(
                "SELECT * FROM learning_questions WHERE id = ? AND owner_id = ?",
                (question_id, owner_id),
            ).fetchone()
        return _row(row)

    def purge_question(self, question_id: str, owner_id: str) -> bool:
        with self._connect() as db:
            db.execute(
                "DELETE FROM learning_attempts WHERE question_id = ? AND owner_id = ?",
                (question_id, owner_id),
            )
            cursor = db.execute(
                "DELETE FROM learning_questions WHERE id = ? AND owner_id = ? "
                "AND deleted_at IS NOT NULL",
                (question_id, owner_id),
            )
        return cursor.rowcount > 0

    def purge_expired_questions(self, owner_id: str | None = None) -> int:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as db:
            params: list[Any] = [now]
            where = "purge_at IS NOT NULL AND purge_at <= ?"
            if owner_id:
                where += " AND owner_id = ?"
                params.append(owner_id)
            ids = [
                row["id"]
                for row in db.execute(
                    f"SELECT id FROM learning_questions WHERE {where}", params
                ).fetchall()
            ]
            for question_id in ids:
                db.execute("DELETE FROM learning_attempts WHERE question_id = ?", (question_id,))
                db.execute("DELETE FROM learning_questions WHERE id = ?", (question_id,))
        return len(ids)

    def update_question_review(
        self,
        question_id: str,
        owner_id: str,
        *,
        due: str,
        streak: int,
        reviewed_at: str,
    ) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE learning_questions SET review_due = ?, review_streak = ?, "
                "last_reviewed_at = ? WHERE id = ? AND owner_id = ?",
                (due, streak, reviewed_at, question_id, owner_id),
            )

    def list_due_questions(self, owner_id: str, today: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM learning_questions "
                "WHERE owner_id = ? AND deleted_at IS NULL "
                "AND library_id IN (SELECT id FROM learning_libraries "
                "WHERE owner_id = ? AND deleted_at IS NULL) "
                "AND review_due != '' AND review_due <= ? "
                "ORDER BY review_due, created_at",
                (owner_id, owner_id, today),
            ).fetchall()
        return [dict(row) for row in rows]

    def review_summary(self, owner_id: str, today: str) -> dict[str, int]:
        with self._connect() as db:
            due = db.execute(
                "SELECT COUNT(*) AS count FROM learning_questions "
                "WHERE owner_id = ? AND deleted_at IS NULL "
                "AND library_id IN (SELECT id FROM learning_libraries "
                "WHERE owner_id = ? AND deleted_at IS NULL) "
                "AND review_due != '' AND review_due <= ?",
                (owner_id, owner_id, today),
            ).fetchone()["count"]
            total = db.execute(
                "SELECT COUNT(*) AS count FROM learning_questions "
                "WHERE owner_id = ? AND deleted_at IS NULL "
                "AND library_id IN (SELECT id FROM learning_libraries "
                "WHERE owner_id = ? AND deleted_at IS NULL)",
                (owner_id, owner_id),
            ).fetchone()["count"]
            reviewed = db.execute(
                "SELECT COUNT(*) AS count FROM learning_questions "
                "WHERE owner_id = ? AND deleted_at IS NULL "
                "AND library_id IN (SELECT id FROM learning_libraries "
                "WHERE owner_id = ? AND deleted_at IS NULL) "
                "AND last_reviewed_at IS NOT NULL",
                (owner_id, owner_id),
            ).fetchone()["count"]
        return {"due": int(due), "total": int(total), "reviewed": int(reviewed)}

    def create_attempt(
        self,
        *,
        question_id: str,
        owner_id: str,
        answer_text: str,
        correctness: str,
        score: float,
        feedback: dict[str, Any],
    ) -> dict[str, Any]:
        row = {
            "id": _id("at"),
            "question_id": question_id,
            "owner_id": owner_id,
            "answer_text": answer_text,
            "correctness": correctness,
            "score": score,
            "feedback_json": json.dumps(feedback, ensure_ascii=False),
            "created_at": _now(),
        }
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO learning_attempts
                    (id, question_id, owner_id, answer_text, correctness, score,
                     feedback_json, created_at)
                VALUES
                    (:id, :question_id, :owner_id, :answer_text, :correctness, :score,
                     :feedback_json, :created_at)
                """,
                row,
            )
        return row

    # ------------------------------------------------------------------
    # 每个学生自己的视觉模型配置（多档案）
    # ------------------------------------------------------------------
    def list_vision_profiles(self, owner_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM learning_vision_profiles WHERE owner_id = ? "
                "ORDER BY is_active DESC, created_at ASC",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_vision_profile(self, profile_id: str, owner_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return _row(
                db.execute(
                    "SELECT * FROM learning_vision_profiles "
                    "WHERE id = ? AND owner_id = ?",
                    (profile_id, owner_id),
                ).fetchone()
            )

    def active_vision_profile(self, owner_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return _row(
                db.execute(
                    "SELECT * FROM learning_vision_profiles "
                    "WHERE owner_id = ? AND is_active = 1 "
                    "ORDER BY created_at ASC LIMIT 1",
                    (owner_id,),
                ).fetchone()
            )

    def create_vision_profile(self, owner_id: str, data: dict[str, Any]) -> dict[str, Any]:
        has_active = self.active_vision_profile(owner_id) is not None
        row = {
            "id": _id("prof"),
            "owner_id": owner_id,
            "name": str(data.get("name") or "模型配置").strip()[:60],
            "provider": str(data.get("provider") or "custom").strip()[:30],
            "model": str(data.get("model") or "").strip()[:80],
            "base_url": str(data.get("base_url") or "").strip()[:300],
            "official_url": str(data.get("official_url") or "").strip()[:300],
            "note": str(data.get("note") or "").strip()[:300],
            "key_cipher": data["key_cipher"],
            "key_mask": data["key_mask"],
            "key_fingerprint": data.get("key_fingerprint") or "",
            "status": "unknown",
            "last_tested_at": None,
            "last_test_message": "",
            "is_active": 0 if has_active else 1,
            "created_at": _now(),
        }
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO learning_vision_profiles
                    (id, owner_id, name, provider, model, base_url,
                     official_url, note, key_cipher, key_mask,
                     key_fingerprint, status, last_tested_at,
                     last_test_message, is_active, created_at)
                VALUES
                    (:id, :owner_id, :name, :provider, :model, :base_url,
                     :official_url, :note, :key_cipher, :key_mask,
                     :key_fingerprint, :status, :last_tested_at,
                     :last_test_message, :is_active, :created_at)
                """,
                row,
            )
        return row

    def update_vision_profile(
        self,
        profile_id: str,
        owner_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        allowed = {"name", "provider", "model", "base_url", "official_url", "note", "status", "last_tested_at", "last_test_message"}
        values = {key: value for key, value in updates.items() if key in allowed}
        if values:
            assignments = ", ".join(f"{key} = ?" for key in values)
            with self._connect() as db:
                db.execute(
                    f"UPDATE learning_vision_profiles SET {assignments} "
                    "WHERE id = ? AND owner_id = ?",
                    (*values.values(), profile_id, owner_id),
                )
        return self.get_vision_profile(profile_id, owner_id)

    def delete_vision_profile(self, profile_id: str, owner_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                "DELETE FROM learning_vision_profiles WHERE id = ? AND owner_id = ?",
                (profile_id, owner_id),
            )
            return cursor.rowcount > 0

    def activate_vision_profile(self, profile_id: str, owner_id: str) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT id FROM learning_vision_profiles WHERE id = ? AND owner_id = ?",
                (profile_id, owner_id),
            ).fetchone()
            if row is None:
                return False
            db.execute(
                "UPDATE learning_vision_profiles SET is_active = 0 WHERE owner_id = ?",
                (owner_id,),
            )
            db.execute(
                "UPDATE learning_vision_profiles SET is_active = 1 "
                "WHERE id = ? AND owner_id = ?",
                (profile_id, owner_id),
            )
            return True

    def update_vision_profile_test(
        self,
        profile_id: str,
        owner_id: str,
        *,
        status: str,
        message: str,
    ) -> dict[str, Any] | None:
        with self._connect() as db:
            db.execute(
                "UPDATE learning_vision_profiles "
                "SET status = ?, last_tested_at = ?, last_test_message = ? "
                "WHERE id = ? AND owner_id = ?",
                (status, _now(), message[:500], profile_id, owner_id),
            )
        return self.get_vision_profile(profile_id, owner_id)

    def get_vision_settings(self, owner_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return _row(
                db.execute(
                    "SELECT * FROM learning_vision_settings WHERE owner_id = ?",
                    (owner_id,),
                ).fetchone()
            )

    def set_vision_settings(
        self,
        owner_id: str,
        *,
        base_url: str,
        model: str,
        api_key_cipher: str | None,
        key_mask: str,
        key_fingerprint: str = "",
    ) -> dict[str, Any]:
        existing = self.get_vision_settings(owner_id)
        cipher = api_key_cipher or (existing or {}).get("api_key_cipher")
        if not cipher:
            raise ValueError("首次配置必须提供 API Key")
        mask = key_mask or (existing or {}).get("key_mask") or "****"
        fingerprint = key_fingerprint or (existing or {}).get("key_fingerprint") or ""
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO learning_vision_settings
                    (owner_id, base_url, model, api_key_cipher, key_mask,
                     key_fingerprint, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(owner_id) DO UPDATE SET
                    base_url = excluded.base_url,
                    model = excluded.model,
                    api_key_cipher = excluded.api_key_cipher,
                    key_mask = excluded.key_mask,
                    key_fingerprint = excluded.key_fingerprint,
                    updated_at = excluded.updated_at
                """,
                (owner_id, base_url, model, cipher, mask, fingerprint, _now()),
            )
        return self.get_vision_settings(owner_id) or {}

    def delete_vision_settings(self, owner_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                "DELETE FROM learning_vision_settings WHERE owner_id = ?",
                (owner_id,),
            )
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # 任务清单
    # ------------------------------------------------------------------
    def create_tasks(self, owner_id: str, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as db:
            for task in tasks:
                row = {
                    "id": _id("task"),
                    "owner_id": owner_id,
                    "title": str(task.get("title") or "学习任务").strip(),
                    "detail": str(task.get("detail") or "").strip(),
                    "duration_min": max(5, int(task.get("duration_min") or 60)),
                    "priority": task.get("priority")
                    if task.get("priority") in {"high", "medium", "low", "none"}
                    else "none",
                    "start_date": str(task.get("start_date") or date.today().isoformat()),
                    "due_date": str(task.get("due_date") or date.today().isoformat()),
                    "remind_at": task.get("remind_at") or None,
                    "status": "pending",
                    "actual_min": 0,
                    "source_exam_id": str(task.get("source_exam_id") or ""),
                    "created_at": _now(),
                    "completed_at": None,
                }
                db.execute(
                    """
                    INSERT INTO learning_tasks
                        (id, owner_id, title, detail, duration_min, priority,
                         start_date, due_date, remind_at, status, actual_min,
                         source_exam_id, created_at, completed_at)
                    VALUES
                        (:id, :owner_id, :title, :detail, :duration_min, :priority,
                         :start_date, :due_date, :remind_at, :status, :actual_min,
                         :source_exam_id, :created_at, :completed_at)
                    """,
                    row,
                )
                rows.append(row)
        return rows

    def list_tasks(self, owner_id: str, on_date: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as db:
            if on_date:
                rows = db.execute(
                    """
                    SELECT * FROM learning_tasks
                    WHERE owner_id = ? AND start_date <= ?
                      AND (due_date >= ? OR status = 'pending')
                    ORDER BY
                      CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1
                                    WHEN 'low' THEN 2 ELSE 3 END,
                      due_date, created_at
                    """,
                    (owner_id, on_date, on_date),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM learning_tasks WHERE owner_id = ? "
                    "ORDER BY due_date, created_at",
                    (owner_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def update_task(self, task_id: str, owner_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {
            "title",
            "detail",
            "duration_min",
            "priority",
            "start_date",
            "due_date",
            "remind_at",
            "status",
            "actual_min",
        }
        values = {key: value for key, value in updates.items() if key in allowed}
        if values.get("status") == "completed":
            values["completed_at"] = _now()
        elif values.get("status") == "pending":
            values["completed_at"] = None
        if not values:
            return self.get_task(task_id, owner_id)
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._connect() as db:
            db.execute(
                f"UPDATE learning_tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                (*values.values(), task_id, owner_id),
            )
        return self.get_task(task_id, owner_id)

    def get_task(self, task_id: str, owner_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return _row(
                db.execute(
                    "SELECT * FROM learning_tasks WHERE id = ? AND owner_id = ?",
                    (task_id, owner_id),
                ).fetchone()
            )

    def delete_task(self, task_id: str, owner_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                "DELETE FROM learning_tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            )
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # 专注
    # ------------------------------------------------------------------
    def start_focus(self, owner_id: str, task_id: str | None, planned_min: int) -> dict[str, Any]:
        row = {
            "id": _id("fs"),
            "owner_id": owner_id,
            "task_id": task_id,
            "mode": "pomodoro",
            "planned_min": max(1, int(planned_min)),
            "started_at": _now(),
            "ended_at": None,
            "actual_min": None,
            "completed": 0,
        }
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO learning_focus
                    (id, owner_id, task_id, mode, planned_min, started_at,
                     ended_at, actual_min, completed)
                VALUES
                    (:id, :owner_id, :task_id, :mode, :planned_min, :started_at,
                     :ended_at, :actual_min, :completed)
                """,
                row,
            )
        return row

    def stop_focus(
        self,
        focus_id: str,
        owner_id: str,
        completed: bool = True,
        *,
        elapsed_seconds: int | None = None,
    ) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM learning_focus WHERE id = ? AND owner_id = ?",
                (focus_id, owner_id),
            ).fetchone()
            if row is None:
                return None
            if row["ended_at"]:
                return dict(row)
            started = datetime.fromisoformat(row["started_at"])
            if elapsed_seconds is not None:
                actual = max(0, round(elapsed_seconds / 60))
            else:
                actual = max(1, round((datetime.now(timezone.utc) - started).total_seconds() / 60))
            db.execute(
                "UPDATE learning_focus SET ended_at = ?, actual_min = ?, completed = ? "
                "WHERE id = ? AND owner_id = ?",
                (_now(), actual, int(completed), focus_id, owner_id),
            )
            if row["task_id"]:
                db.execute(
                    "UPDATE learning_tasks SET actual_min = actual_min + ? "
                    "WHERE id = ? AND owner_id = ?",
                    (actual, row["task_id"], owner_id),
                )
            updated = db.execute(
                "SELECT * FROM learning_focus WHERE id = ? AND owner_id = ?",
                (focus_id, owner_id),
            ).fetchone()
            return _row(updated)

    def active_focus(self, owner_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return _row(
                db.execute(
                    "SELECT * FROM learning_focus WHERE owner_id = ? AND ended_at IS NULL "
                    "ORDER BY started_at DESC LIMIT 1",
                    (owner_id,),
                ).fetchone()
            )

    def focus_today_minutes(self, owner_id: str) -> int:
        today = date.today().isoformat()
        with self._connect() as db:
            row = db.execute(
                "SELECT COALESCE(SUM(actual_min), 0) AS minutes FROM learning_focus "
                "WHERE owner_id = ? AND ended_at IS NOT NULL AND substr(started_at, 1, 10) = ?",
                (owner_id, today),
            ).fetchone()
        return int(row["minutes"] or 0)

    def focus_between(self, owner_id: str, start: str, end: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM learning_focus WHERE owner_id = ? "
                "AND ended_at IS NOT NULL AND substr(started_at, 1, 10) BETWEEN ? AND ? "
                "ORDER BY started_at",
                (owner_id, start, end),
            ).fetchall()
        return [dict(row) for row in rows]

    def task_summary(self, owner_id: str) -> dict[str, int]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT status, COUNT(*) AS count, COALESCE(SUM(actual_min), 0) AS minutes "
                "FROM learning_tasks WHERE owner_id = ? GROUP BY status",
                (owner_id,),
            ).fetchall()
        result = {"pending": 0, "completed": 0, "actual_min": 0}
        for row in rows:
            result[row["status"]] = int(row["count"])
            result["actual_min"] += int(row["minutes"] or 0)
        return result

    def recent_focus(self, owner_id: str, limit: int = 8) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM learning_focus WHERE owner_id = ? AND ended_at IS NOT NULL "
                "ORDER BY started_at DESC LIMIT ?",
                (owner_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # 课程表
    # ------------------------------------------------------------------
    def create_course(self, owner_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": _id("course"),
            "owner_id": owner_id,
            "name": str(data.get("name") or "课程").strip(),
            "teacher": str(data.get("teacher") or "").strip(),
            "weekday": max(1, min(7, int(data.get("weekday") or 1))),
            "start_time": str(data.get("start_time") or "08:00"),
            "end_time": str(data.get("end_time") or "09:40"),
            "location": str(data.get("location") or "").strip(),
            "weeks": str(data.get("weeks") or "").strip(),
            "week_parity": (
                str(data.get("week_parity") or "all")
                if str(data.get("week_parity") or "all") in {"all", "odd", "even"}
                else "all"
            ),
            "assignment": str(data.get("assignment") or "").strip(),
            "created_at": _now(),
        }
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO learning_courses
                    (id, owner_id, name, teacher, weekday, start_time, end_time,
                     location, weeks, week_parity, assignment, created_at)
                VALUES
                    (:id, :owner_id, :name, :teacher, :weekday, :start_time, :end_time,
                     :location, :weeks, :week_parity, :assignment, :created_at)
                """,
                row,
            )
        return row

    def list_courses(self, owner_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM learning_courses WHERE owner_id = ? "
                "ORDER BY weekday, start_time",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def semester_start(self, owner_id: str) -> str:
        with self._connect() as db:
            row = db.execute(
                "SELECT semester_start FROM learning_calendar_settings WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()
        return str(row["semester_start"] or "") if row else ""

    def set_semester_start(self, owner_id: str, value: str) -> str:
        with self._connect() as db:
            db.execute(
                "INSERT INTO learning_calendar_settings(owner_id, semester_start) "
                "VALUES (?, ?) ON CONFLICT(owner_id) DO UPDATE SET semester_start = excluded.semester_start",
                (owner_id, value),
            )
        return value

    # ------------------------------------------------------------------
    # 课程资料
    # ------------------------------------------------------------------
    def get_course(self, course_id: str, owner_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return _row(
                db.execute(
                    "SELECT * FROM learning_courses WHERE id = ? AND owner_id = ?",
                    (course_id, owner_id),
                ).fetchone()
            )

    def add_course_material(
        self,
        owner_id: str,
        course_id: str,
        title: str,
        content: str,
    ) -> dict[str, Any]:
        row = {
            "id": _id("mat"),
            "course_id": course_id,
            "owner_id": owner_id,
            "title": title.strip()[:120],
            "content": content.strip(),
            "created_at": _now(),
        }
        with self._connect() as db:
            db.execute(
                "INSERT INTO learning_course_materials "
                "(id, course_id, owner_id, title, content, created_at) "
                "VALUES (:id, :course_id, :owner_id, :title, :content, :created_at)",
                row,
            )
        return row

    def list_course_materials(self, owner_id: str, course_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM learning_course_materials "
                "WHERE owner_id = ? AND course_id = ? ORDER BY created_at DESC",
                (owner_id, course_id),
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # 考试周
    # ------------------------------------------------------------------
    def create_exam(self, owner_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": _id("exam"),
            "owner_id": owner_id,
            "course_name": str(data.get("course_name") or "考试").strip()[:60],
            "exam_date": str(data.get("exam_date") or date.today().isoformat()),
            "start_time": str(data.get("start_time") or "").strip()[:20],
            "location": str(data.get("location") or "").strip()[:80],
            "note": str(data.get("note") or "").strip()[:300],
            "created_at": _now(),
        }
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO learning_exams
                    (id, owner_id, course_name, exam_date, start_time,
                     location, note, created_at)
                VALUES
                    (:id, :owner_id, :course_name, :exam_date, :start_time,
                     :location, :note, :created_at)
                """,
                row,
            )
        return row

    def list_exams(self, owner_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM learning_exams WHERE owner_id = ? "
                "ORDER BY exam_date, start_time",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_exam(self, exam_id: str, owner_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return _row(
                db.execute(
                    "SELECT * FROM learning_exams WHERE id = ? AND owner_id = ?",
                    (exam_id, owner_id),
                ).fetchone()
            )

    def delete_exam(self, exam_id: str, owner_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                "DELETE FROM learning_exams WHERE id = ? AND owner_id = ?",
                (exam_id, owner_id),
            )
            db.execute(
                "DELETE FROM learning_tasks WHERE owner_id = ? "
                "AND source_exam_id = ? AND status = 'pending'",
                (owner_id, exam_id),
            )
            return cursor.rowcount > 0

    def list_all_questions(self, owner_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM learning_questions WHERE owner_id = ? "
                "AND deleted_at IS NULL "
                "AND library_id IN (SELECT id FROM learning_libraries "
                "WHERE owner_id = ? AND deleted_at IS NULL) "
                "ORDER BY created_at DESC",
                (owner_id, owner_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_pending_exam_tasks(self, owner_id: str, exam_id: str) -> int:
        with self._connect() as db:
            cursor = db.execute(
                "DELETE FROM learning_tasks WHERE owner_id = ? "
                "AND source_exam_id = ? AND status = 'pending'",
                (owner_id, exam_id),
            )
            return cursor.rowcount
