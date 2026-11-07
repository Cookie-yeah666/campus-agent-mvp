"""意图识别路由器。

融合三类信号：
1. 强规则（明确的办事句式、越界请求、寒暄）；
2. 关键词权重（办事词 / 问答词）；
3. 与内置示例句的 TF-IDF 余弦相似度。
输出意图类型、置信度与可解释的命中依据。
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.config import Settings
from app.core.enums import IntentType
from app.models.domain import KnowledgeChunk
from app.retrieval.tokenizer import tokenize
from app.retrieval.vector_search import TfidfVectorIndex

WORKFLOW_EXAMPLES: tuple[str, ...] = (
    "我要补办校园卡",
    "帮我挂失校园卡",
    "校园卡丢了怎么补办",
    "我要开在读证明",
    "宿舍报修怎么弄",
    "我想预约图书馆自习室座位",
    "帮我办理补卡",
    "校园卡补办申请",
    "我要缴纳补卡费用",
    "帮我预约补办时间",
)

QA_EXAMPLES: tuple[str, ...] = (
    "奖学金申请需要什么材料",
    "转专业需要什么条件",
    "校园卡补办要多少钱",
    "图书馆借书能借多久",
    "请假三天找谁审批",
    "考试作弊会被怎么处分",
    "国家助学金一年多少钱",
    "选课什么时候开始",
    "门禁几点关门",
    "电子资源怎么校外访问",
)

HUMAN_EXAMPLES: tuple[str, ...] = (
    "帮我写一首诗",
    "今天天气怎么样",
    "推荐一只股票",
    "讲个笑话",
    "帮我翻译一段英文",
    "帮我写代码",
    "给我讲个故事",
    "怎么赚钱",
    "帮我写一篇论文",
    "推荐一部电影",
)

CLARIFY_EXAMPLES: tuple[str, ...] = (
    "在吗",
    "你好",
    "有人吗",
    "嗯",
    "在不在",
    "help",
    "随便问问",
    "喂",
    "测试",
    "？",
)

WORKFLOW_KEYWORDS: dict[str, float] = {
    "补办": 2.2,
    "补卡": 2.2,
    "挂失": 2.0,
    "报修": 2.4,
    "网络": 2.0,
    "断网": 2.4,
    "报修": 2.2,
    "开证明": 2.2,
    "办理": 1.2,
    "预约": 1.4,
    "缴费": 1.5,
    "申请": 0.6,
    "我要": 0.8,
    "帮我": 0.8,
}

QA_KEYWORDS: dict[str, float] = {
    "是什么": 2.0,
    "怎么回事": 2.0,
    "为什么": 1.4,
    "要求": 1.5,
    "条件": 1.5,
    "规则": 1.5,
    "政策": 1.5,
    "规定": 1.3,
    "哪些": 1.5,
    "有哪些": 1.8,
    "材料": 1.5,
    "标准": 1.3,
    "多少": 1.2,
    "多久": 1.2,
    "什么时候": 1.4,
    "怎么": 0.8,
    "如何": 0.8,
    "流程": 1.0,
    "时间": 0.8,
}

PROMPT_INJECTION_RE = re.compile(
    r"(忽略.{0,8}(指令|提示|规则)|系统提示词|system prompt|泄露.{0,8}(密钥|key|提示词)|"
    r"绕过.{0,6}(限制|审核)|jailbreak|ignore (all|previous)|DAN模式)",
    re.IGNORECASE,
)
OUT_OF_SCOPE_RE = re.compile(
    r"(写.{0,4}诗|作.{0,3}诗|写作文|写代码|编程|翻译|天气|股票|基金|彩票|笑话|星座|游戏|电影|旅游|菜谱|好吃|美食|外卖|手机|租房|房价|健身|医院|看病|演唱会|门票|机票|火车票)"
)
STRONG_WORKFLOW_RE = re.compile(
    r"(我要|我想|帮我|麻烦你?|需要).{0,8}(补办|补卡|挂失|报修|开证明|办理|预约|缴费)"
)
LEAVE_REQUEST_RE = re.compile(r"(我要请假|申请请假|请假申请|办理请假|请个假)")
NETWORK_REQUEST_RE = re.compile(
    r"(报修|维修|断网|没网|无法上网|WiFi|wifi|网线|路由器|网络故障)"
)
CARD_REQUEST_RE = re.compile(r"(校园卡|补卡).{0,6}(补办|丢失|丢了|遗失|坏了|挂失)|补办校园卡")


class RouterResult(BaseModel):
    """路由结果。"""

    intent: IntentType
    confidence: float
    scores: dict[str, float] = Field(default_factory=dict)
    matched_keywords: list[str] = Field(default_factory=list)
    reason: str = ""
    is_follow_up: bool = False


class IntentRouter:
    """混合意图路由器。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        examples: list[tuple[str, str]] = []
        for intent, items in (
            (IntentType.QA, QA_EXAMPLES),
            (IntentType.WORKFLOW, WORKFLOW_EXAMPLES),
            (IntentType.HUMAN_HANDOFF, HUMAN_EXAMPLES),
            (IntentType.CLARIFY, CLARIFY_EXAMPLES),
        ):
            for index, item in enumerate(items):
                examples.append((intent.value, item))
        chunks = [
            KnowledgeChunk(
                chunk_id=f"ex-{intent}-{index:02d}",
                doc_id=intent,
                doc_title=intent,
                chapter="",
                category="intent",
                chunk_index=index,
                content=example,
            )
            for index, (intent, example) in enumerate(examples)
        ]
        self._index = TfidfVectorIndex(chunks)

    def route(
        self,
        text: str,
        *,
        previous_intent: IntentType | None = None,
        has_history: bool = False,
    ) -> RouterResult:
        """识别用户意图。

        Args:
            text: 用户输入。
            previous_intent: 上一轮意图，用于多轮追问。
            has_history: 是否存在历史对话。

        Returns:
            :class:`RouterResult`。
        """
        cleaned = text.strip()
        if not cleaned:
            return RouterResult(
                intent=IntentType.CLARIFY,
                confidence=0.2,
                reason="空输入",
            )

        # 1. 强规则：Prompt 注入优先拦截
        if PROMPT_INJECTION_RE.search(cleaned):
            return RouterResult(
                intent=IntentType.HUMAN_HANDOFF,
                confidence=0.99,
                scores={IntentType.HUMAN_HANDOFF.value: 0.99},
                matched_keywords=[PROMPT_INJECTION_RE.search(cleaned).group(0)],
                reason="疑似 Prompt 注入",
            )

        # 2. 强规则：越界请求
        if OUT_OF_SCOPE_RE.search(cleaned):
            return RouterResult(
                intent=IntentType.HUMAN_HANDOFF,
                confidence=0.94,
                scores={IntentType.HUMAN_HANDOFF.value: 0.94},
                matched_keywords=OUT_OF_SCOPE_RE.findall(cleaned),
                reason="命中越界请求规则",
            )

        # 2. 强规则：明确的办事句式
        if LEAVE_REQUEST_RE.search(cleaned):
            return RouterResult(
                intent=IntentType.WORKFLOW,
                confidence=0.96,
                scores={IntentType.WORKFLOW.value: 0.96},
                matched_keywords=[LEAVE_REQUEST_RE.search(cleaned).group(0)],
                reason="请假申请强规则",
            )
        if NETWORK_REQUEST_RE.search(cleaned):
            return RouterResult(
                intent=IntentType.WORKFLOW,
                confidence=0.97,
                scores={IntentType.WORKFLOW.value: 0.97},
                matched_keywords=[NETWORK_REQUEST_RE.search(cleaned).group(0)],
                reason="网络报修强规则",
            )
        if STRONG_WORKFLOW_RE.search(cleaned) or cleaned in {
            "补办校园卡",
            "校园卡补办",
            "我要补办校园卡",
        }:
            matches = STRONG_WORKFLOW_RE.findall(cleaned)
            keywords = [
                part
                for match in matches
                for part in (match if isinstance(match, tuple) else (match,))
            ]
            return RouterResult(
                intent=IntentType.WORKFLOW,
                confidence=0.96,
                scores={IntentType.WORKFLOW.value: 0.96},
                matched_keywords=keywords,
                reason="命中明确办事句式",
            )

        # 3. 多轮追问：短句 + 上一轮是问答
        tokens = tokenize(cleaned)
        if (
            has_history
            and previous_intent == IntentType.QA
            and (len(cleaned) <= 12 or cleaned.endswith(("呢", "吗")))
        ):
            return RouterResult(
                intent=IntentType.QA,
                confidence=0.86,
                scores={IntentType.QA.value: 0.86},
                reason="结合上一轮问答意图判定为追问",
                is_follow_up=True,
            )

        # 4. 关键词与示例相似度
        matched: list[str] = []
        workflow_keyword_score = 0.0
        for keyword, weight in WORKFLOW_KEYWORDS.items():
            if keyword in cleaned:
                workflow_keyword_score += weight
                matched.append(keyword)
        qa_keyword_score = 0.0
        for keyword, weight in QA_KEYWORDS.items():
            if keyword in cleaned:
                qa_keyword_score += weight
                matched.append(keyword)

        workflow_keyword_score = min(1.0, workflow_keyword_score / 3.5)
        qa_keyword_score = min(1.0, qa_keyword_score / 3.5)

        similarity = self._example_similarity(cleaned)
        scores = {
            IntentType.QA.value: round(0.55 * qa_keyword_score + 0.45 * similarity.get("qa", 0.0), 4),
            IntentType.WORKFLOW.value: round(
                0.55 * workflow_keyword_score + 0.45 * similarity.get("workflow", 0.0), 4
            ),
            IntentType.HUMAN_HANDOFF.value: round(similarity.get("human_handoff", 0.0) * 0.6, 4),
            IntentType.CLARIFY.value: round(
                0.5 * (1.0 if len(cleaned) <= 3 else 0.0) + 0.5 * similarity.get("clarify", 0.0),
                4,
            ),
        }

        best_intent = max(scores, key=lambda key: scores[key])
        confidence = scores[best_intent]

        # 5. 问答与办事的边界修正：疑问句（多少/怎么/条件…）且无办事祈使动词时优先问答
        question_markers = (
            "什么", "多少", "哪些", "怎么", "如何", "多久", "几点", "谁",
            "条件", "材料", "要求", "规定", "标准", "吗", "？", "?",
        )
        imperative_markers = ("我要", "我想", "帮我", "麻烦", "预约", "提交")
        is_question = any(marker in cleaned for marker in question_markers)
        is_imperative = any(marker in cleaned for marker in imperative_markers)
        if best_intent == IntentType.WORKFLOW.value and is_question and not is_imperative:
            best_intent = IntentType.QA.value
            confidence = max(scores[IntentType.QA.value], 0.86)
            scores[IntentType.QA.value] = confidence

        if best_intent == IntentType.WORKFLOW.value and qa_keyword_score >= workflow_keyword_score:
            best_intent = IntentType.QA.value
            confidence = scores[IntentType.QA.value]

        # 5.1 明确的疑问句给问答置信度下限，避免“奖学金申请需要什么材料”
        #     这类只含少量制度关键词的问题被误判为低置信度。
        question_hints = (
            "什么", "哪些", "多少", "怎么", "如何", "多久", "条件",
            "材料", "要求", "规定", "标准", "吗", "？", "?",
        )
        if best_intent == IntentType.QA.value and any(
            hint in cleaned for hint in question_hints
        ):
            confidence = max(confidence, 0.86)
            scores[IntentType.QA.value] = confidence

        # 6. 低置信度先澄清；寒暄/无意义输入直接澄清
        if confidence < 0.35 or (
            len(tokens) <= 1 and best_intent not in {IntentType.WORKFLOW.value, IntentType.QA.value}
        ):
            best_intent = IntentType.CLARIFY.value
            confidence = max(confidence, 0.3)

        return RouterResult(
            intent=IntentType(best_intent),
            confidence=round(float(confidence), 4),
            scores=scores,
            matched_keywords=sorted(set(matched)),
            reason=f"关键词与示例相似度融合，最高分 {confidence:.2f}",
        )

    def _example_similarity(self, text: str) -> dict[str, float]:
        """计算与各类示例句的最大相似度（归一化到 0~1）。"""
        hits = self._index.search(text, top_k=30)
        best: dict[str, float] = {}
        for hit in hits:
            current = best.get(hit.doc_id, 0.0)
            best[hit.doc_id] = max(current, hit.vector_score)
        return {intent: min(1.0, score / 0.35) for intent, score in best.items()}
