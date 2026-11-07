"""查询改写器。

基于规则完成三件事：
1. 口语化转书面语（"咋弄" -> "如何办理"）；
2. 同义词归一（"补卡" -> "校园卡补办"）；
3. 低置信度时生成 2 条改写查询（同义词扩展 + 结合上下文补全）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 口语化 / 简称 -> 书面表达。按长度倒序匹配，避免短词抢先替换。
NORMALIZE_MAP: dict[str, str] = {
    "挂失补卡": "校园卡补办",
    "补办校园卡": "校园卡补办",
    "补办卡": "校园卡补办",
    "补卡": "校园卡补办",
    "咋弄": "如何办理",
    "咋办": "如何办理",
    "怎么弄": "如何办理",
    "要啥": "需要哪些材料",
    "需要啥": "需要哪些材料",
    "啥": "什么",
    "多少钱": "费用 工本费",
    "要多久": "办理时限",
    "多久能": "办理时限",
    "借多久": "借阅期限",
    "几点关门": "关闭时间",
    "几点": "时间",
    "在吗": "",
    "在不在": "",
}

# 同义词扩展：命中左侧词时补充右侧检索词
SYNONYMS: dict[str, tuple[str, ...]] = {
    "校园卡补办": ("补卡", "挂失", "工本费"),
    "奖学金": ("奖助学金", "评奖评优", "国家奖学金"),
    "助学金": ("资助", "困难认定", "国家助学金"),
    "转专业": ("学籍异动", "转入专业", "转专业申请"),
    "图书借阅": ("借书", "续借", "借阅期限"),
    "借阅": ("借书", "续借", "逾期"),
    "自习室": ("座位预约", "图书馆座位", "签到"),
    "请假": ("考勤", "销假", "审批"),
    "考试作弊": ("违纪", "处分", "开除学籍"),
    "补考": ("不及格", "重修", "成绩"),
    "门禁": ("晚归", "通行时间", "校门"),
    "电子资源": ("数据库", "校外访问", "批量下载"),
    "选课": ("学分", "通识课", "退课"),
}

_PRONOUNS = ("它", "这个", "那个", "那", "这", "呢")
_QUESTION_TAIL = re.compile(r"(呢|吗|吧|么)$")


@dataclass
class RewriteResult:
    """一次查询改写的结果。"""

    original: str
    normalized: str
    rewritten: list[str]


class QueryRewriter:
    """规则式查询改写器（可替换为 LLM 改写实现）。"""

    def normalize(self, text: str) -> str:
        """口语化转书面语并做同义词归一。"""
        result = text.strip()
        for source in sorted(NORMALIZE_MAP, key=len, reverse=True):
            target = NORMALIZE_MAP[source]
            if source in result:
                result = result.replace(source, target)
        return re.sub(r"\s+", " ", result).strip()

    def expand_synonyms(self, query: str) -> str:
        """在查询后追加同义词，提升召回。"""
        extras: list[str] = []
        for keyword, synonyms in SYNONYMS.items():
            if keyword in query:
                for synonym in synonyms[:2]:
                    if synonym not in query and synonym not in extras:
                        extras.append(synonym)
        return f"{query} {' '.join(extras)}".strip() if extras else query

    def rewrite(self, query: str, context: list[str] | None = None) -> RewriteResult:
        """生成最多两条改写查询。

        Args:
            query: 归一化后的用户问题。
            context: 最近几轮用户问题（由旧到新）。

        Returns:
            :class:`RewriteResult`，``rewritten`` 最多包含 2 条不同查询。
        """
        normalized = self.normalize(query)
        candidates: list[str] = []

        expanded = self.expand_synonyms(normalized)
        if expanded != normalized:
            candidates.append(expanded)

        needs_context = (
            len(normalized) <= 12
            or any(pronoun in normalized for pronoun in _PRONOUNS)
            or bool(_QUESTION_TAIL.search(normalized))
        )
        if context and needs_context:
            candidates.append(f"{context[-1]} {normalized}".strip())
        else:
            candidates.append(f"{normalized} 规定 条件 标准".strip())

        unique: list[str] = []
        for candidate in candidates:
            if candidate and candidate not in unique and candidate != normalized:
                unique.append(candidate)
        return RewriteResult(original=query, normalized=normalized, rewritten=unique[:2])
