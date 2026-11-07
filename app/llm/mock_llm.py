"""本地 Mock LLM。

不调用任何外部 API：从检索片段中抽取关键句，按问题类型重新组织，
并在每个事实点后插入引用编号。真实模型接入时替换本类即可。
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import re
import time
from typing import Any

from app.config import Settings
from app.llm.base import BaseLLM, LLMResponse
from app.llm.prompt_templates import CONTEXT_END, CONTEXT_START
from app.retrieval.tokenizer import tokenize

# 只在句号/问号/感叹号/换行处断句；分号常用于列举条件，
# 提前切断会丢失“绩点不低于 3.0”等关键条款。
_SENTENCE_RE = re.compile(r"[^。！？\n]+[。！？]?")

MATERIAL_HINTS = ("材料", "准备", "带什么", "需要什么", "要啥")
FEE_HINTS = ("多少钱", "费用", "收费", "工本费", "价格", "金额")
TIME_HINTS = ("多久", "时间", "期限", "几点", "什么时候", "工作日")
CONDITION_HINTS = ("条件", "要求", "资格", "标准", "门槛")
PROCESS_HINTS = ("怎么", "如何", "流程", "办理", "预约", "申请")

OPENING_TEMPLATES: dict[str, list[str]] = {
    "materials": ["需要准备的材料如下：", "办理时通常需要准备这些材料：", "材料清单如下："],
    "fee": ["费用标准如下：", "关于收费，制度中有明确规定：", "费用方面可以这样确认："],
    "time": ["时间安排如下：", "关于办理时限与时间：", "制度中对时间的规定是："],
    "conditions": ["需要同时满足以下条件：", "参评或申请条件包括：", "资格要求如下："],
    "process": ["办理流程如下：", "可以按下面的步骤办理：", "流程与办理方式如下："],
    "general": ["根据校内制度文件，关键信息如下：", "校内制度中的相关规定是：", "检索到的关键条款如下："],
}


class MockLLM(BaseLLM):
    """抽取式 + 模板式的本地模型实现。"""

    name = "mock-deepseek-v3"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> LLMResponse:
        """基于上下文 JSON 生成带引用的回答。"""
        started = time.perf_counter()
        context = self._extract_context(messages)
        query = self._last_user_message(messages)
        strict = any("严格模式" in message.get("content", "") for message in messages)

        if not context:
            content = "根据现有材料无法回答这个问题。"
        else:
            content = self._compose(query, context, temperature=temperature, strict=strict)

        if len(content) > max_tokens * 3:
            content = content[: max_tokens * 3].rstrip() + "……"

        if self._settings.llm_simulate_delay:
            low = self._settings.llm_min_delay_ms / 1000
            high = self._settings.llm_max_delay_ms / 1000
            await asyncio.sleep(random.uniform(low, high) * (0.9 + temperature))

        elapsed = int((time.perf_counter() - started) * 1000)
        prompt_chars = sum(len(message.get("content", "")) for message in messages)
        return LLMResponse(
            content=content,
            model=self._settings.llm_model_name,
            usage={
                "prompt_tokens": math.ceil(prompt_chars / 2),
                "completion_tokens": math.ceil(len(content) / 2),
            },
            latency_ms=elapsed,
        )

    def _extract_context(self, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        """从系统提示中解析检索片段 JSON。"""
        for message in messages:
            content = message.get("content", "")
            start = content.find(CONTEXT_START)
            end = content.find(CONTEXT_END)
            if start == -1 or end == -1:
                continue
            raw = content[start + len(CONTEXT_START) : end].strip()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                return []
            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, dict)]
        return []

    def _last_user_message(self, messages: list[dict[str, str]]) -> str:
        """取最后一条用户消息作为问题。"""
        for message in reversed(messages):
            if message.get("role") == "user":
                return message.get("content", "").strip()
        return ""

    def _compose(
        self,
        query: str,
        context: list[dict[str, Any]],
        *,
        temperature: float,
        strict: bool,
    ) -> str:
        """组织最终回答。"""
        kind = self._classify(query)
        query_tokens = set(tokenize(query))
        lines: list[str] = []
        used_sentences: set[str] = set()

        # 以 Top-1 片段为主，避免把低相关章节拼进回答；
        # 只有主片段不足两条时才补充第二片段。
        for index, chunk in enumerate(context[:2], start=1):
            content = str(chunk.get("content", ""))
            sentences = self._candidate_sentences(
                content,
                query_tokens,
                kind,
                strict=strict,
                limit=3 if index == 1 else 2,
            )
            for sentence in sentences:
                key = re.sub(r"\s+", "", sentence)[:40]
                if key in used_sentences:
                    continue
                used_sentences.add(key)
                lines.append(f"- {sentence} [{index}]")
            if index == 1 and len(lines) >= 2:
                break

        if not lines:
            first = context[0]
            snippet = str(first.get("content", ""))[:120].strip()
            lines.append(f"- {snippet}…… [{1}]")

        opening = self._pick_opening(kind, temperature, query)
        title = str(context[0].get("doc_title", ""))
        if title and kind != "general":
            header = f"根据《{title}》等校内制度，{opening}"
        else:
            header = opening

        closing = "以上内容依据校内制度文件整理，如与最新通知不一致，以主管部门解释为准。"
        return "\n".join([header, "", *lines, "", closing])

    def _pick_opening(self, kind: str, temperature: float, query: str) -> str:
        """按温度选择措辞，温度越高表达略有变化。"""
        options = OPENING_TEMPLATES.get(kind, OPENING_TEMPLATES["general"])
        if temperature < 0.5 or len(options) == 1:
            return options[0]
        seed = hash(query) % len(options)
        return options[seed]

    def _classify(self, query: str) -> str:
        """判断问题关注点，用于选择回答结构。"""
        if any(hint in query for hint in FEE_HINTS):
            return "fee"
        if any(hint in query for hint in TIME_HINTS):
            return "time"
        # “需要什么条件”同时含“需要什么”和“条件”，条件类优先，
        # 否则会漏掉绩点/年级等门槛条款。
        if any(hint in query for hint in CONDITION_HINTS):
            return "conditions"
        if any(hint in query for hint in MATERIAL_HINTS):
            return "materials"
        if any(hint in query for hint in PROCESS_HINTS):
            return "process"
        # “转专业学生呢”这类换话题追问没有显式疑问词，但关注的是门槛
        if "转专业" in query:
            return "conditions"
        return "general"

    def _candidate_sentences(
        self,
        content: str,
        query_tokens: set[str],
        kind: str,
        *,
        strict: bool,
        limit: int,
    ) -> list[str]:
        """从片段中挑选与问题最相关的句子。"""
        sentences = [
            sentence.strip()
            for sentence in _SENTENCE_RE.findall(content.replace("\n", ""))
            if len(sentence.strip()) >= 8
        ]
        if not sentences:
            return []

        if strict:
            return [self._shorten(sentence) for sentence in sentences[:2]]

        kind_hint = {
            "materials": "材料",
            "fee": "元",
            "time": "天",
            "conditions": "条件",
            "process": "办理",
        }.get(kind, "")

        scored: list[tuple[float, int, str]] = []
        for position, sentence in enumerate(sentences):
            tokens = set(tokenize(sentence))
            score = float(len(query_tokens & tokens))
            if any(char.isdigit() for char in sentence):
                score += 0.6
            if kind_hint and kind_hint in sentence:
                score += 1.8
            if sentence.startswith("第") and "条" in sentence[:6]:
                score += 0.2
            scored.append((score, -position, sentence))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = [sentence for score, _, sentence in scored[:limit] if score > 0.5]
        if not selected:
            selected = sentences[:limit]
        return [self._shorten(sentence) for sentence in selected]

    @staticmethod
    def _shorten(sentence: str, limit: int = 180) -> str:
        """压缩过长句子，保留完整语义边界。"""
        sentence = re.sub(r"\s+", " ", sentence).strip()
        if len(sentence) <= limit:
            return sentence
        return sentence[:limit].rstrip("，、；") + "……"
