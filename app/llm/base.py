"""大模型抽象接口。

真实接入 DeepSeek / OpenAI 时，只需实现 :class:`BaseLLM` 的
``chat`` 与 ``stream``，其余业务流程无需改动。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    """模型返回结构。"""

    content: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    finish_reason: str = "stop"
    raw: dict[str, Any] = field(default_factory=dict)


class BaseLLM(ABC):
    """模型抽象基类。"""

    name: str = "base-llm"

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> LLMResponse:
        """同步式对话补全。"""
        raise NotImplementedError

    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> AsyncIterator[str]:
        """流式输出，默认实现按句切分一次性返回的内容。

        真实模型可以覆盖此方法，逐 token 产出。
        """
        response = await self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        buffer = ""
        for char in response.content:
            buffer += char
            if char in "。！？；\n" and len(buffer) >= 8:
                yield buffer
                buffer = ""
        if buffer:
            yield buffer
