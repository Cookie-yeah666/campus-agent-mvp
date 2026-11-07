"""pytest fixtures。

每个测试使用独立的临时数据目录，关闭模拟延迟，保证可重复。
"""

from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, reset_settings_cache
from app.deps import AppContainer, reset_container, set_container
from app.main import create_app
from app.models.schema import ChatRequest, ConfirmRequest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_RUNTIME = PROJECT_ROOT / "runtime_work"


@pytest.fixture()
def tmp_path() -> Path:
    """覆盖 pytest 内置 tmp_path，避免其创建带限制 ACL 的目录。"""
    TEST_RUNTIME.mkdir(parents=True, exist_ok=True)
    directory = TEST_RUNTIME / f"case-{uuid.uuid4().hex[:10]}"
    directory.mkdir()
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture()
def container(tmp_path: Path) -> AppContainer:
    """构建使用临时目录的独立容器。"""
    settings = Settings(
        data_dir=tmp_path / "data",
        student_registry_dir=tmp_path / "registry",
        auth_enabled=False,
        llm_simulate_delay=False,
        tool_simulate_delay=False,
    )
    set_container(None)
    instance = AppContainer(settings)
    set_container(instance)
    yield instance
    set_container(None)


@pytest.fixture()
def send(container: AppContainer):
    """同步发送消息的辅助函数。"""

    def _send(text: str, session_id: str | None = None) -> Any:
        return asyncio.run(
            container.chat_service.send(
                ChatRequest(session_id=session_id, message=text)
            )
        )

    return _send


@pytest.fixture()
def confirm(container: AppContainer):
    """同步提交确认/取消的辅助函数。"""

    def _confirm(session_id: str, action: str = "confirm") -> Any:
        return asyncio.run(
            container.chat_service.confirm(
                session_id, ConfirmRequest(action=action)
            )
        )

    return _confirm


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """启动完整 FastAPI 应用（含生命周期）的测试客户端。"""
    monkeypatch.setenv("CAMPUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CAMPUS_STUDENT_REGISTRY_DIR", str(tmp_path / "registry"))
    monkeypatch.setenv("CAMPUS_AUTH_ENABLED", "false")
    monkeypatch.setenv("CAMPUS_LLM_SIMULATE_DELAY", "false")
    monkeypatch.setenv("CAMPUS_TOOL_SIMULATE_DELAY", "false")
    reset_settings_cache()
    reset_container()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    reset_container()
    reset_settings_cache()
