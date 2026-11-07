"""中文分词与文本归一化。

使用 jieba 分词，配合校园领域自定义词典和停用词表。
所有检索器共享同一套分词结果，保证向量空间与关键词空间一致。
"""

from __future__ import annotations

import re
import unicodedata

import jieba

# 校园领域词汇，避免被 jieba 切碎
DOMAIN_WORDS: tuple[str, ...] = (
    "校园卡",
    "补办",
    "挂失",
    "工本费",
    "卡务中心",
    "奖学金",
    "国家奖学金",
    "国家励志奖学金",
    "助学金",
    "助学贷款",
    "勤工助学",
    "困难认定",
    "转专业",
    "学分绩点",
    "平均学分绩点",
    "补考",
    "重修",
    "缓考",
    "选课",
    "通识课",
    "培养方案",
    "门禁",
    "晚归",
    "违纪处分",
    "留校察看",
    "学术不端",
    "请假",
    "销假",
    "旷课",
    "借阅",
    "续借",
    "预约",
    "逾期",
    "自习室",
    "电子资源",
    "数据库",
    "批量下载",
    "校园网",
    "统一身份认证",
)

# 停用词：疑问词、语气词与高频虚词
STOPWORDS: frozenset[str] = frozenset(
    {
        "的", "了", "是", "在", "我", "你", "他", "她", "它", "我们", "你们", "他们",
        "这", "那", "这个", "那个", "这些", "那些", "之", "与", "和", "及", "或",
        "吗", "呢", "啊", "呀", "吧", "哦", "嗯", "哈", "嘛", "么", "着", "过",
        "就", "也", "都", "很", "还", "又", "再", "才", "只", "把", "被", "让",
        "给", "对", "从", "到", "于", "为", "以", "而", "并", "其", "等", "等等",
        "一个", "一些", "什么", "怎么", "怎样", "如何", "为什么", "哪些", "哪个",
        "多少", "多久", "请问", "麻烦", "帮我", "我想", "我要", "可以", "能否",
        "是否", "需要", "有", "没有", "要", "会", "能", "应该", "一般", "具体",
        "相关", "关于", "一下", "请问一下", "谢谢", "老师", "同学",
        "什么时候", "时候", "何时", "哪天", "几号", "星期几", "开始",
    }
)

_PUNCT_RE = re.compile(r"[\s\u3000!\"#$%&'()*+,\-./:;<=>?@\[\]^_`{|}~，。！？；：、“”‘’（）《》【】·…—]+")
_ZH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

for _word in DOMAIN_WORDS:
    jieba.add_word(_word, freq=10000)


def normalize_text(text: str) -> str:
    """全角转半角、英文小写、压缩空白。"""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_ZH_DIGITS)
    text = text.lower()
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str, *, remove_stopwords: bool = True) -> list[str]:
    """对文本分词并过滤标点、停用词与单字噪声。

    Args:
        text: 原始文本。
        remove_stopwords: 是否移除停用词（标题索引可关闭）。

    Returns:
        按出现顺序排列的词列表（保留重复，供词频统计使用）。
    """
    normalized = normalize_text(text)
    cleaned = _PUNCT_RE.sub(" ", normalized)
    tokens: list[str] = []
    for token in jieba.lcut(cleaned):
        token = token.strip()
        if not token or _PUNCT_RE.fullmatch(token):
            continue
        if token.isdigit():
            tokens.append(token)
            continue
        if len(token) < 2:
            continue
        if remove_stopwords and token in STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def token_set(text: str) -> set[str]:
    """返回去重后的词集合。"""
    return set(tokenize(text))


def highlight_terms(query: str) -> list[str]:
    """提取查询中的关键词（去重、去掉疑问词），用于前端高亮。"""
    seen: list[str] = []
    for token in tokenize(query):
        if token not in seen:
            seen.append(token)
    return seen
