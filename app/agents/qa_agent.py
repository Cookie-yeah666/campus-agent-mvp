"""知识问答 Agent。

完整链路：查询归一化 → 混合检索 → 低置信度改写 → 抽取式生成 →
引用校验 → 不合格重生成 → 仍不合格则拒答转人工。
"""

from __future__ import annotations

import re
from typing import Any

from app.agents.base import AgentReply, BaseAgent, citation_from_result
from app.agents.router import OUT_OF_SCOPE_RE, PROMPT_INJECTION_RE, RouterResult
from app.config import Settings
from app.core.enums import AuditEventType, IntentType, TraceStatus
from app.knowledge.builtin_data import FALSE_PREMISES
from app.knowledge.loader import KnowledgeBase
from app.llm.base import BaseLLM
from app.llm.prompt_templates import (
    CLARIFY_MESSAGE,
    FALSE_PREMISE_PREFIX,
    OUT_OF_SCOPE_TEMPLATE,
    REFUSAL_TEMPLATE,
    build_qa_messages,
)
from app.models.domain import RetrievalResult
from app.models.schema import ChatMessage, ChatSession, Citation, MessageRole, TraceStep
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.tokenizer import tokenize

_CITATION_RE = re.compile(r"\[(\d+)\]")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# 校园制度中的主题实体：用于判断追问是“同一话题深入”还是“换话题”
TOPIC_HINTS: tuple[str, ...] = (
    "转专业", "奖学金", "助学金", "助学贷款", "勤工助学", "资助",
    "校园卡", "补卡", "补办", "挂失", "工本费",
    "借阅", "续借", "逾期", "自习室", "座位",
    "请假", "销假", "旷课", "门禁", "晚归",
    "选课", "学分", "成绩", "补考", "重修", "缓考",
    "作弊", "处分", "电子资源", "数据库", "批量下载",
)


class QAAgent(BaseAgent):
    """基于 RAG 的知识问答 Agent。"""

    name = "qa-agent"

    def __init__(
        self,
        llm: BaseLLM,
        retriever: HybridRetriever,
        knowledge: KnowledgeBase,
        audit: Any,
        settings: Settings,
        logger: Any,
    ) -> None:
        self._llm = llm
        self._retriever = retriever
        self._knowledge = knowledge
        self._audit = audit
        self._settings = settings
        self._logger = logger

    async def handle(
        self,
        session: ChatSession,
        text: str,
        *,
        history: list[ChatMessage] | None = None,
        router_result: Any = None,
        confirmed: bool | None = None,
    ) -> AgentReply:
        """回答用户问题。"""
        del confirmed
        if isinstance(router_result, RouterResult):
            if router_result.intent == IntentType.HUMAN_HANDOFF:
                if PROMPT_INJECTION_RE.search(text):
                    return self._injection_refusal()
                return self._out_of_scope(text)
            if router_result.intent == IntentType.CLARIFY:
                return self._clarify()

        normalized = self._retriever.rewriter.normalize(text)
        if not tokenize(normalized):
            return self._clarify()
        if PROMPT_INJECTION_RE.search(text):
            return self._injection_refusal()
        if OUT_OF_SCOPE_RE.search(text):
            return self._out_of_scope(text)

        premise = self._match_false_premise(text)
        if premise is not None:
            return self._correct_premise(premise, text)

        context_questions = [
            message.content
            for message in (history or [])
            if message.role == MessageRole.USER
        ][-3:]
        retrieval_query = normalized
        is_follow_up = bool(
            getattr(router_result, "is_follow_up", False)
            or len(normalized) <= 12
            or normalized.endswith(("呢", "吗", "吧"))
        )
        current_topics = {hint for hint in TOPIC_HINTS if hint in normalized}
        previous_question = context_questions[-1] if context_questions else ""
        same_topic = any(hint in previous_question for hint in current_topics)
        # 只有“同主题深入”或“纯指代追问（它呢/那材料呢）”才补上一轮问题；
        # “奖学金”之后问“转专业学生呢”属于换话题，不能拼接，否则会答错主题。
        if context_questions and is_follow_up:
            if same_topic or not current_topics:
                retrieval_query = f"{previous_question} {normalized}"
            elif current_topics:
                # 换话题但仍是短追问：补上“条件/要求”，让检索落到具体条款，
                # 而不是停在“总则/适用范围”。
                retrieval_query = f"{normalized} 条件 要求"
        bundle, rewrites = self._retriever.search_for_qa(
            retrieval_query, context=context_questions
        )
        top_score = bundle.top_score
        top_results = bundle.results

        trace: list[TraceStep] = [
            TraceStep(
                type="retrieval",
                title="混合检索",
                detail=(
                    f"{len(top_results)} 条候选，Top-1 置信度 {top_score:.2f}，"
                    f"耗时 {bundle.latency_ms}ms"
                ),
                latency_ms=bundle.latency_ms,
                data={
                    "query": normalized,
                    "top": [
                        {
                            "doc_id": result.doc_id,
                            "doc_title": result.doc_title,
                            "chapter": result.chapter,
                            "score": round(result.score, 3),
                        }
                        for result in top_results[:3]
                    ],
                    "vector_candidates": bundle.vector_candidates,
                    "keyword_candidates": bundle.keyword_candidates,
                },
            )
        ]
        if rewrites:
            trace.append(
                TraceStep(
                    type="rewrite",
                    title="低置信度查询改写",
                    detail="；".join(rewrites),
                    status=TraceStatus.WARNING.value,
                    data={"rewritten": rewrites},
                )
            )

        self._audit.record(
            AuditEventType.RETRIEVAL.value,
            session.id,
            session.current_workflow_id,
            {
                "query": text,
                "normalized": normalized,
                "rewritten": rewrites,
                "top_score": top_score,
                "results": [
                    {
                        "doc_id": result.doc_id,
                        "chunk_id": result.chunk_id,
                        "score": result.score,
                        "coverage": result.coverage,
                    }
                    for result in top_results
                ],
            },
        )

        if not top_results or top_score < self._settings.low_confidence:
            return self._refuse(
                top_results,
                reason="low_confidence",
                trace=trace,
                detail=f"Top-1 置信度 {top_score:.2f} 低于阈值 {self._settings.low_confidence}",
            )

        history_payload = [
            {"role": message.role.value, "content": message.content}
            for message in (history or [])
            if message.role in {MessageRole.USER, MessageRole.ASSISTANT}
        ][-6:]
        generation_query = retrieval_query if is_follow_up else text
        messages = build_qa_messages(generation_query, top_results, history_payload)
        response = await self._llm.chat(
            messages,
            temperature=self._settings.llm_temperature,
            max_tokens=self._settings.llm_max_tokens,
        )
        valid, reasons = self._validate_citations(response.content, top_results)
        trace.append(
            TraceStep(
                type="generation",
                title="生成带引用回答",
                detail=f"{response.model}，{response.usage.get('completion_tokens', 0)} tokens",
                latency_ms=response.latency_ms,
            )
        )

        if not valid:
            trace.append(
                TraceStep(
                    type="validation",
                    title="引用校验未通过，重新生成",
                    detail="；".join(reasons[:3]),
                    status=TraceStatus.WARNING.value,
                )
            )
            strict_messages = messages + [
                {
                    "role": "system",
                    "content": (
                        "严格模式：必须逐字引用材料中的完整句子作为分点，"
                        "不得改写数字与条款，每个分点必须带引用编号。"
                    ),
                }
            ]
            response = await self._llm.chat(
                strict_messages,
                temperature=0.1,
                max_tokens=self._settings.llm_max_tokens,
            )
            valid, reasons = self._validate_citations(response.content, top_results)

        if not valid:
            trace.append(
                TraceStep(
                    type="validation",
                    title="二次校验仍未通过，转人工",
                    detail="；".join(reasons[:3]),
                    status=TraceStatus.FAILED.value,
                )
            )
            return self._refuse(
                top_results,
                reason="citation_invalid",
                trace=trace,
                detail="回答引用无法与检索片段对应",
            )

        citations = self._build_citations(response.content, top_results)
        trace.append(
            TraceStep(
                type="validation",
                title="引用校验通过",
                detail=f"{len(citations)} 条引用可溯源",
                status=TraceStatus.SUCCESS.value,
            )
        )
        if top_score < self._settings.high_confidence:
            trace.insert(
                1,
                TraceStep(
                    type="retrieval",
                    title="置信度一般，已启用二次检索",
                    detail=f"Top-1 {top_score:.2f} < {self._settings.high_confidence}",
                    status=TraceStatus.WARNING.value,
                ),
            )

        return AgentReply(
            content=response.content,
            citations=citations,
            confidence=round(top_score, 4),
            metadata={
                "intent": IntentType.QA.value,
                "normalized_query": normalized,
                "rewritten_queries": rewrites,
                "retrieval_ms": bundle.latency_ms,
                "llm_ms": response.latency_ms,
                "model": response.model,
                "citation_count": len(citations),
                "refused": False,
            },
            trace=trace,
        )

    # ------------------------------------------------------------------ 分支
    def _match_false_premise(self, text: str) -> dict[str, Any] | None:
        """匹配常见错误前提。"""
        for item in FALSE_PREMISES:
            if all(keyword in text for keyword in item["keywords"]):
                return item
        return None

    def _correct_premise(self, premise: dict[str, Any], text: str) -> AgentReply:
        """纠正错误前提，并附上正确条款引用。"""
        chunks = [
            chunk
            for chunk in self._knowledge.chunks
            if chunk.doc_id == premise["doc_id"]
        ]
        chunks.sort(key=lambda chunk: 0 if chunk.chapter in premise["chapters"] else 1)
        selected = chunks[:2]
        citations: list[Citation] = []
        bullet = ""
        if selected:
            chunk = selected[0]
            snippet = chunk.content[:120] + ("…" if len(chunk.content) > 120 else "")
            citations.append(
                Citation(
                    doc_id=chunk.doc_id,
                    doc_title=chunk.doc_title,
                    chapter=chunk.chapter,
                    doc_number=chunk.doc_number,
                    chunk_id=chunk.chunk_id,
                    content_snippet=snippet,
                    score=0.95,
                    category=chunk.category,
                )
            )
            sentence = self._pick_supporting_sentence(chunk.content)
            bullet = f"\n\n- {sentence} [1]"
        content = (
            f"{FALSE_PREMISE_PREFIX}{premise['answer']}{bullet}\n\n"
            "以上依据来自校内制度文件，如与最新通知不一致，以主管部门解释为准。"
        )
        trace = [
            TraceStep(
                type="intent",
                title="识别到错误前提",
                detail=f"命中纠正规则：{premise['id']}",
                status=TraceStatus.WARNING.value,
            ),
            TraceStep(
                type="validation",
                title="引用正确条款",
                detail=f"{len(citations)} 条引用",
            ),
        ]
        return AgentReply(
            content=content,
            citations=citations,
            confidence=0.9,
            metadata={
                "intent": IntentType.QA.value,
                "false_premise": premise["id"],
                "refused": False,
            },
            trace=trace,
        )

    @staticmethod
    def _pick_supporting_sentence(content: str) -> str:
        """挑选能支撑纠正结论的条款句。"""
        sentences = [
            sentence.strip()
            for sentence in re.split(r"[。！？；\n]", content)
            if sentence.strip()
        ]
        keywords = ("不及格", "挂科", "补考", "重修", "20 元", "30 天", "工本费")
        for sentence in sentences:
            if any(keyword in sentence for keyword in keywords):
                return sentence + "。"
        return sentences[0] + "。" if sentences else content[:80]

    def _refuse(
        self,
        results: list[RetrievalResult],
        *,
        reason: str,
        trace: list[TraceStep],
        detail: str = "",
    ) -> AgentReply:
        """知识不足时拒答并转人工。"""
        category = results[0].category if results else None
        contact = self._knowledge.contacts_for_category(category)
        trace.append(
            TraceStep(
                type="handoff",
                title="知识不足，转人工",
                detail=detail or "检索置信度不足",
                status=TraceStatus.WARNING.value,
            )
        )
        return AgentReply(
            content=REFUSAL_TEMPLATE.format(
                department=contact["department"],
                phone=contact["phone"],
            ),
            citations=[],
            confidence=round(results[0].score, 4) if results else 0.0,
            metadata={
                "intent": IntentType.QA.value,
                "refused": True,
                "reason": reason,
                "category": category,
                "contact": contact,
            },
            suggested_actions=["转人工咨询", "换个问法"],
            trace=trace,
        )

    def _injection_refusal(self) -> AgentReply:
        """拒绝修改系统规则、泄露提示词/密钥的请求。"""
        return AgentReply(
            content=(
                "我不能执行修改系统规则、绕过限制或泄露提示词/密钥的请求。"
                "如果你要查询校内办事或制度，我可以继续帮你。"
            ),
            confidence=0.99,
            metadata={"intent": IntentType.HUMAN_HANDOFF.value, "handoff": True, "injection": True},
            suggested_actions=["转人工咨询", "查看办事指南"],
            trace=[
                TraceStep(
                    type="handoff",
                    title="Prompt 注入拦截",
                    detail="检测到修改规则/泄露提示词的请求",
                    status=TraceStatus.WARNING.value,
                )
            ],
        )

    def _out_of_scope(self, text: str) -> AgentReply:
        """越界请求：明确拒绝并转人工。"""
        return AgentReply(
            content=OUT_OF_SCOPE_TEMPLATE,
            confidence=0.95,
            metadata={"intent": IntentType.HUMAN_HANDOFF.value, "handoff": True},
            suggested_actions=["转人工咨询", "查看帮助"],
            trace=[
                TraceStep(
                    type="intent",
                    title="越界请求",
                    detail="不属于校园服务范围",
                    status=TraceStatus.WARNING.value,
                ),
                TraceStep(
                    type="handoff",
                    title="转人工",
                    detail="已给出人工咨询渠道",
                    status=TraceStatus.WARNING.value,
                ),
            ],
        )

    def _clarify(self) -> AgentReply:
        """信息不足时的澄清话术。"""
        return AgentReply(
            content=CLARIFY_MESSAGE,
            confidence=0.3,
            metadata={"intent": IntentType.CLARIFY.value, "clarify": True},
            suggested_actions=["奖学金申请需要什么材料", "我要补办校园卡"],
            trace=[
                TraceStep(
                    type="intent",
                    title="意图不明确",
                    detail="引导用户补充信息",
                    status=TraceStatus.WARNING.value,
                )
            ],
        )

    def _build_citations(
        self,
        answer: str,
        results: list[RetrievalResult],
    ) -> list[Citation]:
        """只保留回答中真正引用的来源。"""
        indices = sorted({int(value) for value in _CITATION_RE.findall(answer)})
        citations: list[Citation] = []
        for index in indices:
            if 1 <= index <= len(results):
                citations.append(citation_from_result(results[index - 1]))
        if not citations and results:
            citations.append(citation_from_result(results[0]))
        return citations

    def _validate_citations(
        self,
        answer: str,
        results: list[RetrievalResult],
    ) -> tuple[bool, list[str]]:
        """校验引用编号、事实数字与语义重合度。"""
        reasons: list[str] = []
        indices = [int(value) for value in _CITATION_RE.findall(answer)]
        if not indices:
            reasons.append("回答缺少引用标记")
        if any(index < 1 or index > len(results) for index in indices):
            reasons.append("引用编号超出检索结果范围")

        bullet_lines = [
            line.strip()
            for line in answer.splitlines()
            if line.strip().startswith(("- ", "• "))
        ]
        if not bullet_lines:
            reasons.append("回答缺少分点结论")

        for line in bullet_lines:
            line_indices = [int(value) for value in _CITATION_RE.findall(line)]
            if not line_indices:
                reasons.append("存在未标注引用的结论")
                continue
            cleaned = _CITATION_RE.sub("", line).lstrip("-• ").strip()
            for index in line_indices:
                if not 1 <= index <= len(results):
                    continue
                content = results[index - 1].content
                for number in _NUMBER_RE.findall(cleaned):
                    if number not in content:
                        reasons.append(f"数字 {number} 未在引用 [{index}] 中找到支撑")
                tokens = set(tokenize(cleaned))
                if tokens:
                    overlap = len(tokens & set(tokenize(content))) / len(tokens)
                    if overlap < 0.35:
                        reasons.append(f"结论与引用 [{index}] 的重合度过低")
        return (not reasons, reasons)
