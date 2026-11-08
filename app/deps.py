"""应用容器（组合根）。

集中装配知识库、检索器、工具、工作流、Agent 与存储，
API、CLI 通过 ``get_container()`` 复用同一套单例。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.agents.qa_agent import QAAgent
from app.agents.router import IntentRouter
from app.auth.service import AuthService
from app.agents.workflow_agent import WorkflowAgent
from app.audit.idempotency import IdempotencyStore
from app.audit.logger import AuditLogger
from app.community import CommunityStore
from app.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.evaluation.runner import EvaluationRunner
from app.integrations.http_campus import HttpCampusService
from app.knowledge.loader import KnowledgeBase
from app.learning.service import LearningService
from app.learning.store import LearningStore
from app.llm.mock_llm import MockLLM
from app.memory.session import SessionManager
from app.memory.store import SessionStore, WorkOrderStore
from app.notifications import NotificationStore
from app.retrieval.hybrid_retriever import HybridRetriever
from app.services.chat import ChatService
from app.student_registry import StudentRegistry
from app.tools.mock_services import MockCampusService
from app.tools.registry import ToolRegistry
from app.workflow.definitions import CARD_REISSUE_WORKFLOW, WORKFLOWS
from app.workflow.engine import WorkflowEngine


class AppContainer:
    """进程级依赖容器。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        settings.ensure_directories()
        configure_logging(settings.log_file, settings.log_level)
        self.logger = get_logger("container")
        self.started_at = datetime.now(timezone.utc)

        self.student_registry = StudentRegistry(settings.student_db_path)
        self.auth = AuthService(settings, self.student_registry)
        self.learning_store = LearningStore(settings.learning_db_path)
        self.learning = LearningService(settings, self.learning_store)
        self.knowledge = KnowledgeBase(settings)
        self.retriever = HybridRetriever(self.knowledge, settings)
        if settings.integration_mode == "http" and settings.integration_base_url:
            self.campus_service = HttpCampusService(settings)
        else:
            self.campus_service = MockCampusService(settings, self.student_registry)
        self.mock_service = self.campus_service
        self.tool_registry = ToolRegistry(self.campus_service, settings)
        self.audit = AuditLogger(settings)
        self.notifications = NotificationStore(settings.data_dir / "notifications.json")
        self.community = CommunityStore(settings.data_dir / "community.db")
        self.idempotency = IdempotencyStore(settings)
        self.workorder_store = WorkOrderStore(settings)
        self.session_store = SessionStore(settings)
        self.session_manager = SessionManager(self.session_store, settings)

        self.engine = WorkflowEngine(
            definitions=WORKFLOWS,
            tool_registry=self.tool_registry,
            workorder_store=self.workorder_store,
            audit=self.audit,
            idempotency=self.idempotency,
            settings=settings,
            logger=self.logger,
        )
        self.llm = MockLLM(settings)
        self.router = IntentRouter(settings)
        self.qa_agent = QAAgent(
            self.llm,
            self.retriever,
            self.knowledge,
            self.audit,
            settings,
            self.logger,
        )
        self.workflow_agent = WorkflowAgent(
            self.engine,
            self.session_manager,
            self.audit,
            settings,
            self.logger,
        )
        self.chat_service = ChatService(
            self.router,
            self.qa_agent,
            self.workflow_agent,
            self.session_manager,
            self.engine,
            self.audit,
            settings,
            self.logger,
        )
        self.evaluation = EvaluationRunner(self.retriever, self.audit, settings)

    @property
    def uptime_seconds(self) -> float:
        """进程已运行秒数。"""
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    def health(self) -> dict[str, Any]:
        """健康检查数据。"""
        return {
            "status": "ok",
            "app": self.settings.app_name,
            "version": self.settings.app_version,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "started_at": self.started_at,
            "knowledge_documents": len(self.knowledge.documents),
            "knowledge_chunks": len(self.knowledge.chunks),
            "sessions": self.session_store.count(),
            "workorders": self.workorder_store.count(),
            "tools": self.tool_registry.names,
            "llm_model": self.settings.llm_model_name,
            "environment": "local",
            "server_time": datetime.now(timezone.utc),
            "data_dir": str(self.settings.data_dir),
        }

    def overview(self) -> dict[str, Any]:
        """系统总览（前端系统页使用）。"""
        report = self.evaluation.latest
        return {
            "health": self.health(),
            "tools": [definition.model_dump() for definition in self.tool_registry.definitions()],
            "workflow": CARD_REISSUE_WORKFLOW.model_dump(),
            "categories": self.knowledge.categories(),
            "workorder_counts": self.workorder_store.counts(),
            "audit_count": self.audit.count(),
            "students": self.mock_service.list_students(),
            "student_registry": self.student_registry.stats(),
            "integration": {
                "mode": self.settings.integration_mode
                if self.settings.integration_base_url or self.settings.integration_mode == "mock"
                else "mock",
                "base_url": self.settings.integration_base_url or None,
                "timeout_seconds": self.settings.integration_timeout_seconds,
            },
            "recent_audit": [log.model_dump(mode="json") for log in self.audit.recent(20)],
            "evaluation": report.model_dump(mode="json") if report else None,
            "retrieval": {
                "top_k": self.settings.final_top_k,
                "high_confidence": self.settings.high_confidence,
                "low_confidence": self.settings.low_confidence,
                "chunk_size": [self.settings.chunk_min_chars, self.settings.chunk_max_chars],
            },
        }


_container: AppContainer | None = None


def build_container(settings: Settings | None = None) -> AppContainer:
    """显式构建容器（测试使用）。"""
    return AppContainer(settings or get_settings())


def get_container() -> AppContainer:
    """获取全局容器，首次调用时构建。"""
    global _container
    if _container is None:
        _container = build_container()
    return _container


def set_container(container: AppContainer | None) -> None:
    """替换全局容器（测试使用）。"""
    global _container
    _container = container


def reset_container() -> None:
    """清空全局容器。"""
    set_container(None)
