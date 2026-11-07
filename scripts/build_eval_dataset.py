"""构建 300 条 silver 评测集。

组成：
- 20 条 base 问题 × 12 个同义改写 = 240 条可答问题；
- 60 条明确越界/无依据问题。

注意：这是 silver set，不是人工金标。每条带 gold 文档、hard negative、
split 与来源标记；正式论文使用前必须抽检/复核。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "evaluation" / "datasets"
OUT.mkdir(parents=True, exist_ok=True)

# 20 条 base：4 类各 5 条，覆盖现有冒烟集的主要知识点
BASE_QUERIES: tuple[tuple[str, str, str], ...] = (
    ("校园卡补办要多少钱", "reg-card", "规章"),
    ("校园卡挂失后多久能拿到新卡", "reg-card", "规章"),
    ("补办校园卡需要带什么证件", "reg-card", "规章"),
    ("校门晚上几点关闭", "reg-access", "规章"),
    ("晚归会怎么处理", "reg-access", "规章"),
    ("转专业需要什么条件", "acad-transfer", "教务"),
    ("转专业可以申请几个专业", "acad-transfer", "教务"),
    ("课程不及格可以补考吗", "acad-assessment", "教务"),
    ("补考成绩怎么算", "acad-assessment", "教务"),
    ("每学期最多选多少学分", "acad-course-selection", "教务"),
    ("奖学金申请需要什么材料", "affairs-scholarship", "学工"),
    ("国家奖学金多少钱", "affairs-scholarship", "学工"),
    ("国家助学金分几档", "affairs-financial-aid", "学工"),
    ("助学贷款最多能贷多少", "affairs-financial-aid", "学工"),
    ("请假三天找谁审批", "affairs-leave", "学工"),
    ("图书借阅期限是多久", "lib-borrow", "图书馆"),
    ("图书逾期一天罚多少钱", "lib-borrow", "图书馆"),
    ("自习室座位怎么预约", "lib-study-room", "图书馆"),
    ("自习室违约几次会被暂停", "lib-study-room", "图书馆"),
    ("校外怎么访问电子资源", "lib-e-resource", "图书馆"),
)

PARAPHRASES: tuple[str, ...] = (
    "{q}",
    "请问{q}？",
    "{q}，能说明一下吗？",
    "我想了解{q}",
    "关于{q}，学校是怎么规定的？",
    "{q}有哪些要求？",
    "麻烦查一下{q}",
    "根据校内制度，{q}？",
    "{q}的具体标准是什么？",
    "学生手册里{q}怎么写的？",
    "如果我想知道{q}，该看哪份文件？",
    "帮我确认一下：{q}",
)

NEGATIVE_TOPICS: tuple[str, ...] = (
    "学校附近有什么好吃的火锅",
    "学校附近有什么好吃的烧烤",
    "学校附近哪家奶茶好喝",
    "最近有什么电影推荐",
    "今天股票行情怎么样",
    "基金怎么买",
    "彩票中奖概率",
    "放假去哪里旅游",
    "学校附近酒店推荐",
    "机票怎么买便宜",
    "推荐一个好玩的游戏",
    "买什么手机好",
    "电脑配置怎么选",
    "学校附近租房多少钱",
    "快递怎么寄",
    "外卖哪家好吃",
    "健身房怎么办卡",
    "养宠物要注意什么",
    "驾照怎么考",
    "演唱会门票怎么抢",
)

NEGATIVE_VARIANTS: tuple[str, ...] = (
    "{q}",
    "我想了解{q}",
    "帮我查一下{q}",
)

# hard negative 的粗略配对：同主题不同文档，或相近但不应命中的文档
HARD_NEGATIVE = {
    "reg-card": "reg-access",
    "reg-access": "reg-discipline",
    "acad-transfer": "acad-assessment",
    "acad-assessment": "acad-transfer",
    "acad-course-selection": "acad-assessment",
    "affairs-scholarship": "affairs-financial-aid",
    "affairs-financial-aid": "affairs-scholarship",
    "affairs-leave": "reg-discipline",
    "lib-borrow": "lib-study-room",
    "lib-study-room": "lib-borrow",
    "lib-e-resource": "lib-borrow",
}


def build() -> tuple[list[dict], dict]:
    rows: list[dict] = []
    for base, doc_id, category in BASE_QUERIES:
        for index, template in enumerate(PARAPHRASES):
            question = template.format(q=base)
            # 同一 base 的 12 条按 3 dev / 9 test 切分，保证四类都有 dev
            split = "dev" if index < 3 else "test"
            rows.append(
                {
                    "id": f"qa-{len(rows) + 1:04d}",
                    "split": split,
                    "category": category,
                    "question": question,
                    "answerability": "answerable",
                    "gold_doc_ids": [doc_id],
                    "hard_negatives": [HARD_NEGATIVE.get(doc_id, "reg-card")],
                    "source": "silver_paraphrase",
                    "review_status": "silver",
                    "note": "同义改写，需抽检；不是人工金标。",
                }
            )

    for topic_index, topic in enumerate(NEGATIVE_TOPICS):
        for index, template in enumerate(NEGATIVE_VARIANTS):
            question = template.format(q=topic)
            rows.append(
                {
                    "id": f"qa-{len(rows) + 1:04d}",
                    "split": "test",
                    "category": "越界",
                    "question": question,
                    "answerability": "unanswerable",
                    "gold_doc_ids": [],
                    "hard_negatives": [],
                    "source": "silver_negative",
                    "review_status": "silver",
                    "note": "明确越界/无校内依据，期望拒答或转人工。",
                    "_topic_index": topic_index,
                }
            )

    # 取前 50 条 test 问题作为 hidden holdout 标记，答辩前不查看
    test_rows = [row for row in rows if row["split"] == "test"]
    for row in test_rows[:50]:
        row["hidden_holdout"] = True
    for row in rows:
        row.pop("_topic_index", None)
    return rows, {
        "name": "qa_300_silver",
        "version": "1.0",
        "total": len(rows),
        "answerable": sum(1 for row in rows if row["answerability"] == "answerable"),
        "unanswerable": sum(1 for row in rows if row["answerability"] == "unanswerable"),
        "dev": sum(1 for row in rows if row["split"] == "dev"),
        "test": sum(1 for row in rows if row["split"] == "test"),
        "hidden_holdout": sum(1 for row in rows if row.get("hidden_holdout")),
        "review_status": "silver",
    }


def main() -> None:
    rows, manifest = build()
    path = OUT / "qa_300.jsonl"
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    manifest["sha256"] = digest
    manifest["path"] = str(path)
    (OUT / "qa_300.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {len(rows)} rows -> {path}")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
