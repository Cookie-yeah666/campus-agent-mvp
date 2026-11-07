"""提示词与话术模板。

所有提示词集中在本模块，便于评审、版本管理与后续接入真实模型。
"""

from __future__ import annotations

import json
from typing import Any

CONTEXT_START = "<<<CONTEXT_JSON>>>"
CONTEXT_END = "<<<END_CONTEXT_JSON>>>"

QA_SYSTEM_PROMPT = """你是苏州大学校园智能服务助手「知行」，负责回答校园规章、教务、学工与图书馆相关的问题。

【身份与职责】
- 你只回答与本校校园服务有关的问题，不闲聊、不创作、不提供校外生活建议。
- 你的知识边界是下面提供的校内制度材料，不得使用材料之外的事实。

【回答要求】
1. 只基于给定的检索片段回答，禁止编造制度条款、金额、期限和办理地点。
2. 用简洁的分点表述，每个结论后面必须标注引用编号，例如 [1]。
3. 引用编号必须与材料编号一一对应，不得引用不存在的编号。
4. 如果材料不足以回答，明确说明“校内制度中没有找到可靠依据”，不要猜测。
5. 语言使用简体中文，语气专业、克制、可执行。

【引用格式】
- 每个事实点独立成行，以“- ”开头，行末标注 [n]。
- 开头可以用一句话概括结论，但概括中的事实也必须能在材料中找到依据。

【上下文】
下面是本次检索到的校内制度片段（JSON），编号即引用编号：
{context}
"""

INTENT_SYSTEM_PROMPT = """你是校园服务意图分类器。判断用户输入属于以下哪一类：
- qa：知识问答（问政策、条件、材料、流程、时间、地点、费用等）
- workflow：办事办理（补办、报修、开证明、预约、缴费等明确的办理请求）
- human_handoff：超出校园服务范围，需要转人工
- clarify：信息不足，无法判断
只输出 JSON：{"intent": "qa|workflow|human_handoff|clarify", "confidence": 0.0-1.0, "reason": "..."}。
"""

PARAMETER_EXTRACT_PROMPT = """你是办事流程的参数抽取器。从用户输入中抽取以下字段：
- student_id：10 位数字学号
- campus：校区，只能是“天赐庄”“独墅湖”“阳澄湖”之一
只输出 JSON：{"student_id": "...", "campus": "...", "missing": ["..."], "invalid": ["..."]}。
不要编造用户没有提供的值。
"""

# 办事流程各节点的用户话术
WORKFLOW_MESSAGES: dict[str, str] = {
    "ask_params": (
        "好的，我来帮你办理校园卡补办。\n\n"
        "请提供你的**学号**和**校区**，例如：`2025001001，独墅湖`。\n"
        "校区只能是天赐庄、独墅湖、阳澄湖之一。"
    ),
    "ask_params_again": "还差一些信息：{missing}。请补充后我再继续办理。",
    "invalid_params": "信息格式不太对：{invalid}。学号应为 10 位数字，校区只能是天赐庄、独墅湖、阳澄湖。",
    "confirm": (
        "已为你完成前置校验，请确认以下办理信息：\n\n"
        "- 学号：{student_id}\n"
        "- 校区：{campus}\n"
        "- 预约时段：{slot}\n"
        "- 制卡工本费：{fee} 元\n"
        "- 需携带：本人身份证或学生证\n\n"
        "确认提交后将生成制卡工单，预计 3 个工作日内完成制卡。"
    ),
    "cancelled": "已取消本次校园卡补办申请，未提交任何制卡工单。如需重新办理，随时告诉我。",
    "arrears": (
        "查询到你的校园卡存在欠费 **{amount} 元**，暂时无法提交补办申请。\n\n"
        "请先通过“校园卡服务”充值或到卡务窗口缴清欠费，再重新发起补办。"
    ),
    "invalid_student": "没有查询到学号 **{student_id}** 的学籍信息，请核对后重新输入 10 位学号。",
    "timeout": (
        "业务系统响应超时，我已经自动重试 1 次仍未成功。为了不耽误你，"
        "已为你生成人工处理记录，学号和校区信息都已保留，人工客服会继续处理。"
    ),
    "duplicate": (
        "检测到你今天已经提交过校园卡补办申请（幂等键相同），"
        "本次没有重复生成工单，直接返回原回执：**{receipt}**。"
    ),
    "success": (
        "校园卡补办工单已提交成功。\n\n"
        "- 回执编号：**{receipt}**\n"
        "- 预约时段：{slot}\n"
        "- 取卡地点：{location}\n"
        "- 预计完成：3 个工作日内\n"
        "- 工本费：{fee} 元（领取时缴纳）\n\n"
        "请携带本人身份证或学生证按时前往。凭回执编号可随时查询办理进度。"
    ),
}

# 知识不足时的标准拒答话术
REFUSAL_TEMPLATE = (
    "这个问题我暂时没有找到可靠的校内依据，为了不误导你，我帮你转人工咨询。\n\n"
    "你也可以直接联系 **{department}**，电话 **{phone}**。\n\n"
    "如果你问的是校园规章、教务、奖助或图书馆相关事项，可以换个说法再问我。"
)

OUT_OF_SCOPE_TEMPLATE = (
    "抱歉，这个问题超出了校园服务助手的职责范围，我不能提供这类内容。\n\n"
    "我可以帮你查询校内制度、办理校园卡补办等业务。如需其他帮助，"
    "建议联系 **学生服务大厅**（0512-6716-0000）转人工咨询。"
)

CLARIFY_MESSAGE = (
    "我在的。你可以直接描述要办的事或要查的制度，例如：\n\n"
    "- 奖学金申请需要什么材料？\n"
    "- 校园卡补办要多少钱？\n"
    "- 我要补办校园卡\n\n"
    "我会自动判断是知识问答还是办事办理。"
)

WELCOME_MESSAGE = (
    "你好，我是**知行**，校园智能服务助手。\n\n"
    "我可以：\n"
    "- 基于校内制度回答问题，并给出可核验的引用来源；\n"
    "- 办理校园卡补办，自动校验挂失、欠费并生成回执；\n"
    "- 在知识不足或系统异常时转人工，并保留完整上下文。\n\n"
    "试着问我：“奖学金申请需要什么材料？”"
)

HELP_MESSAGE = """可用命令：
/help      查看帮助
/new       新建会话
/history   查看当前会话历史
/audit     查看当前会话审计轨迹
/workorders 查看最近工单
/quit      退出

也可以直接输入问题，例如：
- 奖学金申请需要什么材料？
- 我要补办校园卡
"""

FALSE_PREMISE_PREFIX = "你的理解可能有一些偏差，我先纠正一下：\n\n"

TITLE_TEMPLATE = "{first_message}"


def build_context_payload(results: list[Any]) -> str:
    """把检索结果序列化为提示词中的上下文 JSON。

    Args:
        results: :class:`app.models.domain.RetrievalResult` 列表。

    Returns:
        带边界标记的 JSON 字符串。
    """
    payload = [
        {
            "index": index,
            "doc_title": result.doc_title,
            "doc_number": result.doc_number,
            "chapter": result.chapter,
            "content": result.content,
            "score": result.score,
        }
        for index, result in enumerate(results, start=1)
    ]
    return f"{CONTEXT_START}\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n{CONTEXT_END}"


def build_qa_messages(
    query: str,
    results: list[Any],
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """构造问答 Agent 的消息列表。

    Args:
        query: 用户问题。
        results: 检索结果。
        history: 最近几轮对话（role/content）。

    Returns:
        OpenAI 风格的消息列表。
    """
    system = QA_SYSTEM_PROMPT.format(context=build_context_payload(results))
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for item in history or []:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": query})
    return messages
