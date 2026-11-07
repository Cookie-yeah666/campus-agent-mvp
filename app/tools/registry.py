"""工具注册表。

工具类通过 ``@register_tool`` 装饰器注册；注册表负责实例化、
按名称查找、统一超时与异常兜底。工具异常不会抛给上层 Agent。
"""

from __future__ import annotations

import asyncio
import time

from app.config import Settings
from app.core.exceptions import ToolTimeoutError
from app.models.domain import ToolDefinition, ToolResult
from app.tools.base import BaseTool
from app.tools.mock_services import MockCampusService

_REGISTERED_TOOL_CLASSES: list[type[BaseTool]] = []


def register_tool(tool_class: type[BaseTool]) -> type[BaseTool]:
    """注册工具类（装饰器）。"""
    if not tool_class.name:
        raise ValueError(f"工具 {tool_class.__name__} 缺少 name")
    if any(existing.name == tool_class.name for existing in _REGISTERED_TOOL_CLASSES):
        raise ValueError(f"工具名称重复: {tool_class.name}")
    _REGISTERED_TOOL_CLASSES.append(tool_class)
    return tool_class


class ToolRegistry:
    """工具注册与执行中心。"""

    def __init__(self, service: MockCampusService, settings: Settings) -> None:
        self._settings = settings
        self._tools: dict[str, BaseTool] = {
            tool_class.name: tool_class(service) for tool_class in _REGISTERED_TOOL_CLASSES
        }

    def get(self, name: str) -> BaseTool | None:
        """按名称获取工具。"""
        return self._tools.get(name)

    @property
    def names(self) -> list[str]:
        """全部工具名称。"""
        return sorted(self._tools)

    def definitions(self) -> list[ToolDefinition]:
        """全部工具定义，供 API 与前端展示。"""
        return [tool.definition() for _, tool in sorted(self._tools.items())]

    async def execute(self, name: str, arguments: dict[str, object]) -> ToolResult:
        """执行工具，统一处理超时与异常。

        Args:
            name: 工具名。
            arguments: 关键字参数。

        Returns:
            :class:`ToolResult`，任何异常都会转换为失败结果。
        """
        tool = self.get(name)
        if tool is None:
            return ToolResult.fail(f"未注册的工具: {name}")
        started = time.perf_counter()

        def _elapsed() -> int:
            return int((time.perf_counter() - started) * 1000)

        try:
            result = await asyncio.wait_for(
                tool.execute(**arguments),
                timeout=self._settings.tool_timeout_seconds,
            )
            result.latency_ms = _elapsed()
            return result
        except asyncio.TimeoutError:
            return ToolResult.fail(
                f"工具 {name} 调用超时（>{self._settings.tool_timeout_seconds}s）",
                latency_ms=_elapsed(),
                timed_out=True,
            )
        except ToolTimeoutError as exc:
            return ToolResult.fail(str(exc), latency_ms=_elapsed(), timed_out=True)
        except Exception as exc:  # noqa: BLE001 - 工具异常必须兜底
            return ToolResult.fail(
                f"工具 {name} 执行失败: {exc}",
                latency_ms=_elapsed(),
            )
