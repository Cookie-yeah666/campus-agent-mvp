"""内置检索冒烟集。

覆盖四类知识库，每题标注标准文档，用于计算 Recall@5 与 MRR@5。
与需求文档中的“50 条检索冒烟集”相比规模较小，但保留了同样的
评测口径，可在不依赖外部数据的情况下复现。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalQuery:
    """一条评测查询。"""

    query: str
    doc_id: str
    category: str


EVAL_QUERIES: tuple[EvalQuery, ...] = (
    # 规章类
    EvalQuery("校园卡补办要多少钱", "reg-card", "规章"),
    EvalQuery("校园卡挂失后多久能拿到新卡", "reg-card", "规章"),
    EvalQuery("补办校园卡需要带什么证件", "reg-card", "规章"),
    EvalQuery("校门晚上几点关闭", "reg-access", "规章"),
    EvalQuery("晚归会怎么处理", "reg-access", "规章"),
    EvalQuery("考试作弊会被开除吗", "reg-discipline", "规章"),
    EvalQuery("处分多久可以解除", "reg-discipline", "规章"),
    # 教务类
    EvalQuery("转专业需要什么条件", "acad-transfer", "教务"),
    EvalQuery("转专业可以申请几个专业", "acad-transfer", "教务"),
    EvalQuery("课程不及格可以补考吗", "acad-assessment", "教务"),
    EvalQuery("补考成绩怎么算", "acad-assessment", "教务"),
    EvalQuery("每学期最多选多少学分", "acad-course-selection", "教务"),
    EvalQuery("开学第几周可以退课", "acad-course-selection", "教务"),
    # 学工类
    EvalQuery("奖学金申请需要什么材料", "affairs-scholarship", "学工"),
    EvalQuery("国家奖学金多少钱", "affairs-scholarship", "学工"),
    EvalQuery("国家助学金分几档", "affairs-financial-aid", "学工"),
    EvalQuery("助学贷款最多能贷多少", "affairs-financial-aid", "学工"),
    EvalQuery("请假三天找谁审批", "affairs-leave", "学工"),
    EvalQuery("请假超过七天怎么办", "affairs-leave", "学工"),
    # 图书馆类
    EvalQuery("图书借阅期限是多久", "lib-borrow", "图书馆"),
    EvalQuery("图书逾期一天罚多少钱", "lib-borrow", "图书馆"),
    EvalQuery("自习室座位怎么预约", "lib-study-room", "图书馆"),
    EvalQuery("自习室违约几次会被暂停", "lib-study-room", "图书馆"),
    EvalQuery("校外怎么访问电子资源", "lib-e-resource", "图书馆"),
    EvalQuery("电子资源可以批量下载吗", "lib-e-resource", "图书馆"),
)
