"""会话管理。

负责创建会话、追加消息、生成标题、维护上下文窗口
以及工作流变量与当前工单的绑定。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.memory.store import SessionStore
from app.models.schema import ChatMessage, ChatSession, MessageRole


def _now() -> datetime:
    """当前 UTC 时间。"""
    return datetime.now(timezone.utc)


class SessionManager:
    """多轮会话管理器。"""

    DEFAULT_TITLE = "新的对话"

    def __init__(self, store: SessionStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    @property
    def store(self) -> SessionStore:
        """底层存储。"""
        return self._store

    def create(self, title: str | None = None, owner: Any | None = None) -> ChatSession:
        """创建空会话，并记录归属。"""
        timestamp = _now()
        owner_id = None
        owner_role = None
        owner_college = None
        if owner is not None and not getattr(owner, "anonymous", False):
            owner_role = getattr(owner, "role", None)
            owner_college = getattr(owner, "college", None)
            owner_id = (
                getattr(owner, "student_id", None)
                if owner_role == "student"
                else getattr(owner, "username", None)
            )
        session = ChatSession(
            id=f"cs-{uuid.uuid4().hex[:12]}",
            title=title or self.DEFAULT_TITLE,
            created_at=timestamp,
            updated_at=timestamp,
            owner_id=owner_id,
            owner_role=owner_role,
            owner_college=owner_college,
        )
        self._store.save(session)
        return session

    def get(self, session_id: str) -> ChatSession:
        """获取会话。"""
        return self._store.get(session_id)

    def list(self) -> list[ChatSession]:
        """列出会话。"""
        return self._store.list()

    def delete(self, session_id: str) -> None:
        """删除会话。"""
        self._store.delete(session_id)

    def save(self, session: ChatSession) -> None:
        """持久化会话。"""
        session.updated_at = _now()
        self._store.save(session)

    def append(self, session: ChatSession, message: ChatMessage) -> ChatMessage:
        """追加消息，必要时自动生成标题。"""
        session.messages.append(message)
        session.updated_at = message.timestamp
        if (
            message.role == MessageRole.USER
            and session.title == self.DEFAULT_TITLE
        ):
            title = message.content.strip().replace("\n", " ")
            session.title = title[: self._settings.session_title_length] or self.DEFAULT_TITLE
        self._store.save(session)
        return message

    def recent_history(
        self,
        session: ChatSession,
        *,
        rounds: int = 3,
    ) -> list[dict[str, str]]:
        """返回最近若干轮的问答上下文。"""
        limit = max(1, rounds) * 2
        history: list[dict[str, str]] = []
        for message in session.messages[-limit:]:
            if message.role in {MessageRole.USER, MessageRole.ASSISTANT}:
                history.append({"role": message.role.value, "content": message.content})
        return history

    def recent_user_questions(self, session: ChatSession, limit: int = 3) -> list[str]:
        """返回最近几条用户问题（不含当前输入）。"""
        questions = [
            message.content
            for message in session.messages
            if message.role == MessageRole.USER
        ]
        return questions[-limit:]

    def set_workflow(self, session: ChatSession, workorder_id: str | None) -> None:
        """绑定或清除当前工单。"""
        session.current_workflow_id = workorder_id
        self._store.save(session)

    def update_variables(self, session: ChatSession, variables: dict[str, Any]) -> None:
        """更新工作流变量。"""
        session.variables.update(variables)
        self._store.save(session)
