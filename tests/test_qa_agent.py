"""知识问答 Agent 测试。"""

from __future__ import annotations

from app.core.enums import IntentType
from app.deps import AppContainer


def test_answer_with_scholarship_citation(container: AppContainer, send) -> None:
    """奖学金材料问题应返回带校内制度引用的回答。"""
    response = send("奖学金申请需要什么材料？")
    assert response.intent == IntentType.QA.value
    assert response.message.citations
    assert any(
        citation.doc_id == "affairs-scholarship"
        for citation in response.message.citations
    )
    assert "材料" in response.message.content
    assert "个人陈述" in response.message.content
    assert response.message.confidence and response.message.confidence > 0.7


def test_card_fee_answer_contains_20_yuan(container: AppContainer, send) -> None:
    """补卡费用回答必须包含 20 元与对应引用。"""
    response = send("校园卡补办要多少钱")
    assert "20 元" in response.message.content
    assert any(
        citation.doc_id == "reg-card" for citation in response.message.citations
    )
    # 回答中的引用编号应与引用卡片数量一致
    assert "[1]" in response.message.content or "[2]" in response.message.content


def test_multi_turn_follow_up(container: AppContainer, send) -> None:
    """追问应结合上一轮上下文命中转专业制度。"""
    first = send("转专业需要什么条件？")
    second = send("转专业学生呢", first.session_id)
    assert second.intent == IntentType.QA.value
    assert second.message.citations
    assert any(
        citation.doc_id == "acad-transfer"
        for citation in second.message.citations
    )
    # 追问必须答到具体门槛，而不是只命中“总则”
    assert "3.0" in second.message.content or "不及格" in second.message.content
    assert second.message.metadata.get("normalized_query")


def test_follow_up_topic_switch(container: AppContainer, send) -> None:
    """在奖学金话题后追问转专业，不能被上一轮问题带偏。"""
    first = send("奖学金申请需要什么材料？")
    second = send("转专业学生呢", first.session_id)
    assert second.message.citations
    assert any(
        citation.doc_id == "acad-transfer"
        for citation in second.message.citations
    )
    assert "3.0" in second.message.content or "不及格" in second.message.content


def test_false_premise_correction(container: AppContainer, send) -> None:
    """错误前提必须被纠正，并引用正确条款。"""
    response = send("奖学金是不是挂科也能拿")
    assert "不准确" in response.message.content
    assert "不及格" in response.message.content
    assert response.message.citations
    assert any(
        citation.doc_id == "affairs-scholarship"
        for citation in response.message.citations
    )


def test_insufficient_knowledge_refuses(container: AppContainer, send) -> None:
    """知识库外的问题应拒答并给出转人工渠道。"""
    response = send("学校附近有什么好吃的火锅")
    assert response.intent == "human_handoff"
    assert response.message.metadata.get("handoff") is True
    assert not response.message.citations
    assert "转人工" in response.message.content


def test_trace_has_retrieval_and_validation(container: AppContainer, send) -> None:
    """问答轨迹应包含检索、生成与引用校验。"""
    response = send("图书借阅期限是多久")
    step_types = {step.type for step in response.trace}
    assert "retrieval" in step_types
    assert "generation" in step_types
    assert "validation" in step_types
