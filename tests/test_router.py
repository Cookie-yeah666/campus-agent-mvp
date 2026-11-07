"""意图路由测试。"""

from __future__ import annotations

from app.core.enums import IntentType
from app.deps import AppContainer


def test_router_detects_workflow(container: AppContainer) -> None:
    """明确办事句式应路由到办事流程且高置信度。"""
    result = container.router.route("我要补办校园卡")
    assert result.intent == IntentType.WORKFLOW
    assert result.confidence > 0.9
    assert result.matched_keywords


def test_router_detects_qa(container: AppContainer) -> None:
    """政策材料类问题应路由到问答且置信度超过 0.85。"""
    result = container.router.route("奖学金申请需要什么材料")
    assert result.intent == IntentType.QA
    assert result.confidence > 0.85


def test_router_follow_up_uses_context(container: AppContainer) -> None:
    """多轮追问结合上一轮意图判定为问答。"""
    result = container.router.route(
        "转专业学生呢",
        previous_intent=IntentType.QA,
        has_history=True,
    )
    assert result.intent == IntentType.QA
    assert result.is_follow_up is True
    assert result.confidence >= 0.8


def test_router_clarify(container: AppContainer) -> None:
    """寒暄或信息不足时返回澄清意图。"""
    result = container.router.route("在吗")
    assert result.intent == IntentType.CLARIFY


def test_router_out_of_scope(container: AppContainer) -> None:
    """越界创作请求应转人工。"""
    result = container.router.route("帮我写一首诗")
    assert result.intent == IntentType.HUMAN_HANDOFF
    assert result.confidence > 0.9


def test_router_fee_question_is_qa(container: AppContainer) -> None:
    """“要多少钱”是政策咨询，不是办事办理。"""
    result = container.router.route("校园卡补办要多少钱")
    assert result.intent == IntentType.QA
