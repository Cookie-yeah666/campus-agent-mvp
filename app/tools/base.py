"""工具基类。

每个工具声明名称、描述、JSON Schema 参数与超时时间，
执行结果统一为 :class:`ToolResult`，异常在注册表层被捕获。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from app.models.domain import ToolDefinition, ToolResult
from app.tools.mock_services import MockCampusService


class BaseTool(ABC):
    """校园业务工具抽象基类。"""

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    parameters_schema: ClassVar[dict[str, Any]] = {}
    timeout_seconds: ClassVar[int] = 5
    category: ClassVar[str] = "校园业务"

    def __init__(self, service: MockCampusService) -> None:
        self._service = service

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行工具并返回统一结果。"""
        raise NotImplementedError

    def definition(self) -> ToolDefinition:
        """返回工具元数据。"""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters_schema=self.parameters_schema,
            timeout_seconds=self.timeout_seconds,
            category=self.category,
        )

    def _require(self, arguments: dict[str, Any], *keys: str) -> None:
        """校验必填参数。

        Raises:
            ValueError: 缺少必填参数。
        """
        missing = [key for key in keys if not arguments.get(key)]
        if missing:
            raise ValueError(f"缺少参数: {', '.join(missing)}")
