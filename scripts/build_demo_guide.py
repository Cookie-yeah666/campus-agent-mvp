"""生成零基础演示脚本（DOCX / PDF 源 / Markdown）。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SHOTS = DOCS / "screenshots"
DIAGRAMS = DOCS / "diagrams"
OUT_DOCX = DOCS / "DEMO_GUIDE.docx"
OUT_MD = DOCS / "DEMO_GUIDE.md"

FONT = "微软雅黑"
CODE_FONT = "Consolas"
INK = "18263A"
INDIGO = "2F5F9E"
TEAL = "357A5F"
AMBER = "A46A2F"
LINE = "D8D2C4"

Blocks: list[tuple[Any, ...]] = []


def h1(text: str, newpage: bool = True) -> None:
    Blocks.append(("h1", text, newpage))


def h2(text: str) -> None:
    Blocks.append(("h2", text))


def p(text: str) -> None:
    Blocks.append(("p", text))


def bullets(items: list[str]) -> None:
    Blocks.append(("bullets", items))


def table(headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> None:
    Blocks.append(("table", headers, rows, widths))


def callout(kind: str, title: str, text: str) -> None:
    Blocks.append(("callout", kind, title, text))


def code(text: str) -> None:
    Blocks.append(("code", text.strip("\n")))


def image(filename: str, caption: str, width: float = 16.0) -> None:
    Blocks.append(("image", filename, caption, width))


def pagebreak() -> None:
    Blocks.append(("pagebreak",))


# =====================================================================
# 内容
# =====================================================================

h1("先看这一页")
p("这份脚本是给**第一次上台、不熟悉计算机**的同学准备的。你不需要懂技术，只需要会三件事：")
bullets(
    [
        "用鼠标左键点按钮。",
        "在白色的输入框里打字。",
        "按键盘上的回车键（Enter）。",
    ]
)
callout(
    "success",
    "整场只需要 5 个动作",
    "登录用「管理员」演示账号 → 问一个问题 → 点一下引用 → 办一张校园卡 → 点确认 → 看工单。其他页面都是给老师看的，时间不够可以跳过。",
)
p("**如果出错超过 30 秒，不要修。** 直接打开 docs/screenshots 文件夹，用截图继续讲。后面“出问题怎么办”那一页写了具体怎么做。")
callout(
    "info",
    "不要背技术名词",
    "你不需要说“RAG、向量、阈值、幂等”。照着加粗的字念就行。老师问技术细节时，把问题转给团队里负责技术的同学。",
)
p("整场 8 分钟，建议这样分配。时间不够就砍掉追问和评测，保住问答、补办、回执。")
table(
    ["时间", "这一段", "你要做什么"],
    [
        ["0:00–2:00", "问答 + 引用", "问奖学金材料，点 [1] 看原文"],
        ["2:00–3:30", "追问 + 拒答", "问转专业，再问一个它不会的火锅"],
        ["3:30–6:30", "补办 + 回执", "新建对话，输 2025001011，确认提交"],
        ["6:30–8:00", "工单 + 评测", "看节点轨迹，切评测中心，收尾"],
    ],
    [2.6, 4.6, 9.4],
)

h1("上台前 20 分钟：照着这张表做")
table(
    ["时间", "你要做什么", "看到什么算成功"],
    [
        ["T-20", "双击项目文件夹里的 START_DEMO.bat", "会弹出一个黑色窗口，然后浏览器打开登录页"],
        ["T-15", "点「工作人员」→「管理员」", "进入工作台；左下角显示“系统管理员”"],
        ["T-10", "把“提词卡”那一页打印，或存到手机里", "手边有输入顺序"],
        ["T-5", "插好投屏线，按 Win+P 选择“复制”", "投影上出现和电脑一样的画面"],
        ["T-5", "浏览器按 Ctrl+0，恢复 100% 大小", "字不重叠、不超出屏幕"],
        ["T-2", "看左侧会话列表", "有 5 个会话，最新一个是“校园卡补办 · 天赐庄”"],
        ["T-0", "深呼吸，开始念开场白", "计时 8 分钟"],
    ],
    [2.0, 9.0, 5.6],
)
p("**学生登录**：切到「学生登录」，输入名册中的学号、姓名和学号后六位；演示主线仍用管理员账号。")
p("**个人中心**：左下角点姓名，可看个人资料、切换账户、退出登录。")
p("**演示开始前，桌面上只留 3 样东西：**")
bullets(
    [
        "浏览器窗口：地址是 127.0.0.1:8000，不要用百度去搜。",
        "黑色服务窗口：标题是 Campus Agent Server，最小化即可，不要关。",
        "打印出来的提词卡：放在键盘旁边，演示时只看它。",
    ]
)
callout(
    "warn",
    "三个不要",
    "不要关掉黑色服务窗口；不要自己安装或更新任何软件；不要删除 data 文件夹。",
)
callout(
    "info",
    "找不到 START_DEMO.bat",
    "它在项目文件夹最外层，和 app、docs 在同一个地方。提前让技术同学把它放到桌面，并自己双击试一次。",
)

h1("屏幕上都是什么")
p("下面这张图里，红圈是你需要认识的区域。你实际只会用到 1、4、5。")
image("diagrams/ui-map.png", "图 1 演示界面地图（红圈对应下表）", 16.0)
table(
    ["编号", "名称", "你要用它做什么"],
    [
        ["1", "新建对话", "每演示一个新话题，先点它，避免和上一段混在一起"],
        ["2", "左侧导航", "切到工单中心、审计回放、评测中心"],
        ["3", "最近会话", "不用点；老师问“刚才的记录呢”时指一下"],
        ["4", "输入框", "点一下，光标闪了再打字"],
        ["5", "发送按钮", "也可以直接按回车键"],
        ["6", "执行轨迹", "不用操作，指给老师看“每一步都有记录”"],
    ],
    [1.6, 4.0, 11.0],
)
p("**中间的白色卡片**是工单确认卡，确认按钮在卡片最下面，下一页有放大图。")

h1("开场 30 秒 + 第一个问题")
p("**你站着说：**")
callout(
    "info",
    "开场白（可以照着念）",
    "老师好，我演示的是校园智能服务助手。它做两件事：第一，回答校园制度问题，每句话都能找到出处；"
    "第二，直接办理校园卡补办，最后给回执。下面我用 8 分钟走一遍。",
)
table(
    ["步骤", "你做什么", "屏幕上会出现什么"],
    [
        ["1", "点左上角的「新建对话」", "中间变成欢迎页，左侧多一个会话"],
        ["2", "点页面最下面的白色输入框", "输入框边框变蓝，光标在闪"],
        ["3", "用键盘输入：奖学金申请需要什么材料？", "字出现在输入框里"],
        ["4", "按回车键（Enter），或点蓝色「发送」", "出现“正在识别意图…”"],
        ["5", "等 2 到 3 秒，不要连续点", "出现 3 条带 [1] 的回答，下面有一张引用卡片"],
    ],
    [1.2, 7.0, 8.4],
)
p("**你指着回答说：**“每条结论后面的 [1] 就是出处；下面这张卡片写着文件名、章节和文号。”")
image("diagrams/ui-citation.png", "图 2 引用卡片：红框里就是回答的依据", 9.5)
p("**再点一下正文里的 [1]，或点卡片右下角「查看原文」**，让老师看到原文。")
callout(
    "warn",
    "如果没反应",
    "先等 3 秒；只点一次发送；还不行按 F5 刷新页面。不要连续点十几次。",
)

h1("追问一句，再问一个它不会的")
p("**第一句，输入：**")
code("转专业需要什么条件？")
p("你会看到它给出绩点 3.0、无不及格、年级等条件。")
p("**第二句，输入：**")
code("转专业学生呢")
p("它会记得上一句在问转专业，继续回答具体门槛。你指着右侧说：“它记得上下文。”")
p("**第三句，输入：**")
code("学校附近有什么好吃的火锅")
p("它会说“没有找到可靠的校内依据”，给出学生工作部电话，并且**没有引用**。")
p("**你这样说：**“它不是什么都答。找不到依据就拒答并转人工，避免编造制度。”")
callout(
    "info",
    "时间够再加一句",
    "输入“奖学金是不是挂科也能拿”，它会先纠正“这个说法不准确”，再引用正确条款。",
)
p("这三句话，分别让老师看到三件事：")
table(
    ["你输入", "证明给老师看"],
    [
        ["转专业需要什么条件？", "回答有依据，不是随口说"],
        ["转专业学生呢", "它记得上一句，能多轮追问"],
        ["学校附近有什么好吃的火锅", "知道边界，找不到依据就不编"],
    ],
    [8.0, 8.4],
)

h1("补办：从输入到确认")
p("这一段是整场最重要的。**只用 2025001011 这个学号**，不要用 2025001002。")
table(
    ["步骤", "你输入什么", "屏幕上会出现什么"],
    [
        ["1", "点「新建对话」，输入：我要补办校园卡", "它问你要学号和校区，并给出示例"],
        ["2", "故意输错：2025001，独墅湖", "它提醒“学号不是 10 位数字”，停在原步骤"],
        ["3", "输入正确的：2025001011，天赐庄", "出现确认卡片：学号、校区、预约时段、20 元、身份证"],
        ["4", "指着卡片说：写入前必须人工确认", "卡片状态是“待确认”"],
    ],
    [1.2, 7.0, 8.4],
)
p("**确认卡片长这样，红框里是你要点的按钮：**")
image("diagrams/ui-card.png", "图 3 确认卡片（示意；你操作时学号会显示 2025001011）", 11.0)
callout(
    "warn",
    "唯一需要记住的学号",
    "完整办理用 2025001011，天赐庄。它已经挂失、没有欠费，所以能一次走完。"
    "如果它提示“今天已经提交过”，说明这个学号今天用过了，换 2025001008，或双击 START_DEMO.bat 重来。",
)

h1("点确认、拿回执、看工单")
table(
    ["步骤", "你做什么", "屏幕上会出现什么"],
    [
        ["1", "点红框里的「确认提交」", "按钮变灰，出现“正在提交”"],
        ["2", "等 1 到 2 秒", "出现回执编号 CARD 开头，状态“已完成”，显示取卡地点"],
        ["3", "点回执旁边的复制图标（可选）", "右上角提示“已复制到剪贴板”"],
        ["4", "点「查看工单」", "右侧打开抽屉：节点轨迹、审计留痕"],
        ["5", "用鼠标滚轮往下滚一点", "能看到“参数抽取→校验学籍→查挂失→查欠费→确认→提交→回执”"],
    ],
    [1.2, 7.0, 8.4],
)
p("**你这样说：**“一次对话，替代原来跑三个窗口。回执编号可以拿去取卡，也可以在工单中心查。”")
callout(
    "warn",
    "如果看不到确认按钮",
    "把鼠标放到聊天区域，往下滚一格滚轮；卡片在消息最下面。",
)
p("**回执出来以后，指给老师看这 3 个地方：**")
table(
    ["位置", "说明"],
    [
        ["回执编号（CARD 开头）", "这是取卡凭据，也可以拿去窗口查询"],
        ["状态“已完成”", "说明系统真的生成了工单，不是只回一句“好的”"],
        ["取卡地点 / 时间", "告诉用户下一步去哪里、什么时候去"],
    ],
    [6.0, 10.4],
)

h1("给老师看证据：工单中心 + 审计回放")
h2("工单中心")
table(
    ["步骤", "你点什么", "屏幕上会出现什么"],
    [
        ["1", "点左侧「工单中心」", "四张统计卡：全部、已完成、待跟进、异常与转人工"],
        ["2", "点「已完成」筛选", "只剩已完成的工单"],
        ["3", "点 2025001002 那一行", "右侧抽屉：回执、学号/校区、预约时段、取卡地点"],
        ["4", "展开「节点轨迹」", "每一步的名称、耗时、状态"],
    ],
    [1.2, 7.0, 8.4],
)
h2("审计回放")
p("点左侧「审计回放」→ 把事件类型筛选为「工具调用」→ 随便展开一条。你不必读 JSON，只说一句：")
callout(
    "success",
    "这一段的唯一台词",
    "“每个关键动作都能在审计里找到对应的输入、输出和时间，所以出了问题可以回放。”",
)
image("diagrams/ui-workorder.png", "图 4 工单中心：状态统计、筛选和办理记录", 15.5)

h1("可选：学生库（1 分钟）")
p("如果老师问“这些学生数据从哪来”，点左侧「学生库」。这个入口只有管理员、辅导员、审计员可见；用管理员登录即可。时间不够可以跳过，不影响主线。")
table(
    ["步骤", "你做什么", "屏幕上会出现什么"],
    [
        ["1", "点左侧「学生库」", "361 条学生、1 个学院、1 届、10 个班、2 个专业"],
        ["2", "专业筛选选“计算机科学与技术”", "剩下 162 条"],
        ["3", "搜索框输入：2527405001，按回车", "出现该生的姓名、班级、届别；手机号显示为 136****7843"],
        ["4", "把筛选切回“全部专业”", "恢复 361 条"],
    ],
    [1.2, 7.4, 8.0],
)
p("**你这样说：**“这是从 Excel 导入的 25 届计科院名册。换一个学院或一届，只要再导入一次，不用改代码。”")
callout(
    "info",
    "学生库的边界",
    "姓名、班级、专业来自名册；校园卡挂失和余额仍是模拟数据。手机号只显示前三位和后四位，原始号码不通过页面暴露。",
)
p("如果老师追问“换一个学院怎么办”，把这条命令指给他看：")
code(
    "python scripts/import_students.py \\\n"
    "  --file students_2026_business.xlsx \\\n"
    "  --cohort 2026 --college 商学院"
)

h1("评测中心 + 收尾")
p("点左侧「评测中心」，指一下四个数字：")
bullets(
    [
        "Recall@5：100%——25 道测试题都能找到正确的制度文件。",
        "MRR@5：100%——正确文件基本都排在第一位。",
        "平均时延：不到 1 毫秒——这是本地检索，不含模型生成。",
        "评测集：25 条——覆盖规章、教务、学工、图书馆四类。",
    ]
)
p("**你这样说：**“这是检索测试，不是答案准确率。目标是 85%，目前全部命中；答案质量还要靠引用校验和人工评测。”")
callout(
    "info",
    "收尾白（照着念）",
    "以上就是演示：有依据、能办事、可追溯。谢谢老师。",
)
image("screenshots/06-evaluation.png", "图 5 评测中心：四个指标和逐题结果", 14.0)

h1("如果只有 5 分钟")
table(
    ["时间", "你做什么", "一句话"],
    [
        ["0:00", "点「管理员」登录，打开工作台", "“一个工作台，问答、办事、审计都在里面。”"],
        ["0:30", "输入：奖学金申请需要什么材料？", "“每个结论都有出处。”"],
        ["1:30", "点 [1] / 查看原文", "“可以回到制度原文。”"],
        ["2:30", "新建对话 → 我要补办校园卡 → 2025001011，天赐庄", "“它先核对，再让我确认。”"],
        ["4:00", "点确认提交", "“一次对话拿到回执。”"],
        ["4:30", "点查看工单", "“每一步都能查。”"],
        ["5:00", "切评测中心，收尾", "“检索目标 85%，目前全部命中。”"],
    ],
    [1.8, 9.0, 5.8],
)
p("**如果只有 3 分钟，只做这 4 步：**")
bullets(
    [
        "问一个奖学金问题，点一下 [1]，说“每个结论都有出处”。",
        "新建对话，输入「我要补办校园卡」，再输入 2025001011，天赐庄，点确认。",
        "点查看工单，说“每一步都能查”。",
        "说收尾白，结束。",
    ]
)
callout(
    "info",
    "压缩版的原则",
    "宁可少讲一个场景，也不要加快语速。老师听不清，讲再多也没用。",
)
callout(
    "success",
    "5 分钟版只讲三句话",
    "有出处、有回执、能回放。把这三句讲清楚，比把六个页面都点一遍更有效。",
)

h1("老师可能问的 8 个问题")
table(
    ["老师问", "你就这样答"],
    [
        ["这是真的系统吗？", "是能跑的原型。制度文本和演示会话是模拟的，但学生名册、问答、补办、回执、审计流程都是真的。"],
        ["为什么不用真的大模型？", "为了现场稳定、不联网。模型接口已经留好，换成真模型不用改流程。"],
        ["它会不会胡说？", "找不到校内依据就拒答；回答必须带引用，引用对不上会重新生成或转人工。"],
        ["能办别的事吗？", "目前只开通校园卡补办，其他事项转人工。这是故意的范围控制，先把一条流程做扎实。"],
        ["重复提交怎么办？", "同一天、同一学号只生成一张工单，再提交会返回原来的回执。"],
        ["数据安全吗？", "演示会话和一卡通状态是模拟的；25 届计科院名册是课程授权导入的，页面只显示脱敏手机号，原始号码不出服务端。"],
        ["你和团队做了什么？", "我负责演示和流程验证，技术实现由团队共同完成；具体模块我可以请负责的同学补充。"],
        ["下一步做什么？", "接真实模型和校园业务系统，扩大评测集，再开通更多办事流程。"],
    ],
    [5.0, 11.4],
)
callout(
    "info",
    "不会答时的统一话术",
    "“这个问题涉及实现细节，我请负责这块的同学补充一下。”说完就把话筒递过去，不要硬编。",
)

h1("出问题怎么办")
table(
    ["你看到的现象", "先做什么", "还不行怎么办"],
    [
        ["浏览器打不开 / 一片空白", "看黑色 Campus Agent Server 窗口还在不在", "双击 START_DEMO.bat，等 15 秒；再不行用截图"],
        ["输入后没反应", "等 3 秒，按一次回车", "按 F5 刷新；仍不行用截图"],
        ["出现“今天已经提交过”", "这是正常现象，不是报错", "换 2025001008，或双击 START_DEMO.bat"],
        ["看不到确认按钮", "鼠标放到聊天区，往下滚一格", "点右侧“执行轨迹”下方，找到当前工单"],
        ["投影上字太小", "浏览器按 Ctrl 和加号两下", "按 Ctrl+0 恢复"],
        ["投影没有画面", "按 Win+P，选“复制”", "换一根 HDMI 线或找现场老师"],
        ["说错一句话", "不要重复道歉，继续下一步", "老师没注意到，别主动回头解释"],
        ["系统卡住超过 30 秒", "不要现场修", "打开 docs/screenshots，用 01、02、03 截图继续讲"],
    ],
    [5.2, 6.4, 5.0],
)
callout(
    "warn",
    "兜底原则",
    "演示不是考试。超过 30 秒没恢复，就切截图，把时间留给“为什么这样设计”。",
)
p("**上台前，把这 4 样东西放在手边：**")
table(
    ["应急物品", "放在哪里", "什么时候用"],
    [
        ["打印的提词卡", "键盘旁边", "忘记下一步时，低头看一眼"],
        ["docs/screenshots 文件夹", "桌面快捷方式", "系统卡住，切图片继续讲"],
        ["这份 DEMO_GUIDE.pdf", "手机里", "PDF 可以放大，随时查步骤"],
        ["技术同学电话", "手机通讯录", "超过 2 分钟没恢复，直接打电话"],
    ],
    [5.4, 5.4, 5.6],
)

h1("绝对不能做的 7 件事")
bullets(
    [
        "不要用 2025001002 演示完整补办——它今天已经提交过，会直接返回旧回执。",
        "不要连续用同一个学号演示两次完整补办——第二次一定命中重复提交。",
        "不要关掉黑色 Campus Agent Server 窗口——关了网页就打不开。",
        "不要删除 data 文件夹——删了数据就没了；要重来就双击 START_DEMO.bat。",
        "不要现场安装、更新 Python 或浏览器。",
        "不要说“准确率 100%”——100% 是 25 道检索题，不是所有问题。",
        "不要和报错较劲超过 30 秒。",
    ]
)
p("**如果已经发生了，按这张表补救，不要慌：**")
table(
    ["已经发生的事", "怎么补救"],
    [
        ["用了 2025001002 演示补办", "换 2025001008 再走一次；或者直接说“这张是预置回执，我们换一张新卡”"],
        ["连续用了 2025001011 两次", "第二次会返回原回执；换 2025001008，或双击 START_DEMO.bat"],
        ["关掉了黑色服务窗口", "双击 START_DEMO.bat，等 15 秒，网页会重新打开"],
        ["删掉了 data 文件夹", "双击 START_DEMO.bat，它会重新生成演示数据"],
    ],
    [6.4, 10.0],
)
callout(
    "success",
    "记住",
    "重置不丢人。现场能继续讲下去，比“保住刚才那一步”重要得多。",
)

h1("一页纸提词卡（打印这一页）")
p("把这一页放在手边，演示时只看这一页。")
table(
    ["顺序", "你输入 / 你点", "你说"],
    [
        ["开场", "—", "“它做两件事：回答有出处，办事有回执。”"],
        ["问答", "奖学金申请需要什么材料？", "“每个结论都有 [1] 出处。”"],
        ["引用", "点 [1] / 查看原文", "“可以回到制度原文。”"],
        ["追问", "转专业需要什么条件？ → 转专业学生呢", "“它记得上一句。”"],
        ["拒答", "学校附近有什么好吃的火锅", "“找不到依据就拒答，不编。”"],
        ["补办", "新建 → 我要补办校园卡 → 2025001011，天赐庄", "“先核对，再让我确认。”"],
        ["确认", "点「确认提交」", "“一次对话拿到回执。”"],
        ["工单", "点「查看工单」", "“每一步都能查。”"],
        ["评测", "点「评测中心」", "“25 题全命中，目标 85%。”"],
        ["收尾", "—", "“有依据、能办事、可追溯。谢谢老师。”"],
    ],
    [1.8, 8.4, 6.2],
)
callout(
    "info",
    "紧张时就说这三句",
    "①“这一步我换个方式展示”，然后切截图。②“这个问题请负责技术的同学补充”，把话筒递过去。"
    "③“我们先把主线走完，细节会后交流”，继续下一页。",
)

h1("数据小抄 + 一键重来")
table(
    ["你想演示", "用这个学号", "会看到"],
    [
        ["完整办成（推荐）", "2025001011，天赐庄", "确认卡片 → 回执"],
        ["完整办成（备用）", "2025001008，独墅湖", "确认卡片 → 回执"],
        ["自动挂失", "2025001006，独墅湖", "轨迹里出现 report_loss"],
        ["欠费拦截", "2025001010，独墅湖", "欠费 8.50 元，工单失败"],
        ["工具超时", "2025000999，独墅湖", "重试后转人工"],
        ["学号无效", "2025009999，独墅湖", "提示学号错误"],
        ["取消办理", "左侧预置会话「校园卡补办 · 天赐庄」→ 取消", "状态变为已取消"],
    ],
    [4.4, 7.2, 5.0],
)
h2("两个双击就能用的文件")
table(
    ["文件", "什么时候双击", "会发生什么"],
    [
        ["START_DEMO.bat", "每次上台前", "自动关旧服务、清数据、重启、生成演示数据、打开网页"],
        ["OPEN_DEMO.bat", "演示中途网页被关了", "只重新打开网页，不动数据"],
    ],
    [4.0, 6.0, 6.4],
)
callout(
    "success",
    "重来一次",
    "双击 START_DEMO.bat，等浏览器自动打开。看到左侧 5 个会话，就是准备好了。",
)

# =====================================================================
# 渲染
# =====================================================================


def set_font(run, name: str = FONT, size: float | None = None, color: str | None = None) -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def add_rich(paragraph, text: str, size: float | None = None, color: str | None = None) -> None:
    for part in re.split(r"(\*\*.+?\*\*)", text):
        if not part:
            continue
        bold = part.startswith("**") and part.endswith("**") and len(part) > 4
        if bold:
            part = part[2:-2]
        run = paragraph.add_run(part)
        run.bold = bold
        set_font(run, FONT, size, color)


def shade(cell, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def borders(table, color: str = LINE, size: int = 4) -> None:
    tbl_pr = table._tbl.tblPr
    border = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = OxmlElement(f"w:{edge}")
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), str(size))
        node.set(qn("w:space"), "0")
        node.set(qn("w:color"), color)
        border.append(node)
    tbl_pr.append(border)


def margins(table, value: int = 90) -> None:
    tbl_pr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side in ("top", "left", "bottom", "right"):
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    tbl_pr.append(mar)


def repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def no_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    split = OxmlElement("w:cantSplit")
    split.set(qn("w:val"), "true")
    tr_pr.append(split)


def add_table(doc, headers: list[str], rows: list[list[str]], widths: list[float] | None) -> None:
    table_obj = doc.add_table(rows=1, cols=len(headers))
    table_obj.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_obj.autofit = False
    tbl_pr = table_obj._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)
    borders(table_obj)
    margins(table_obj)
    if widths:
        total = sum(widths)
        widths = [w * 16.6 / total for w in widths]
    else:
        widths = [16.6 / len(headers)] * len(headers)
    for index, width in enumerate(widths):
        table_obj.columns[index].width = Cm(width)

    header_row = table_obj.rows[0]
    repeat_header(header_row)
    no_split(header_row)
    for index, title in enumerate(headers):
        cell = header_row.cells[index]
        cell.width = Cm(widths[index])
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        shade(cell, INK)
        para = cell.paragraphs[0]
        para.paragraph_format.space_after = Pt(0)
        para.paragraph_format.line_spacing = 1.1
        run = para.add_run(title)
        run.bold = True
        set_font(run, FONT, 9.5, "FFFFFF")

    for row_index, values in enumerate(rows):
        row = table_obj.add_row()
        no_split(row)
        for index, value in enumerate(values):
            cell = row.cells[index]
            cell.width = Cm(widths[index])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            if row_index % 2 == 1:
                shade(cell, "F8F7F2")
            para = cell.paragraphs[0]
            para.paragraph_format.space_after = Pt(0)
            para.paragraph_format.line_spacing = 1.25
            add_rich(para, str(value), 9.8, INK)
    spacer(doc)


def spacer(doc, height: float = 2) -> None:
    para = doc.add_paragraph()
    fmt = para.paragraph_format
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    fmt.line_spacing = Pt(height)
    fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    para.add_run(" ").font.size = Pt(1)


def add_callout(doc, kind: str, title: str, text: str) -> None:
    fill, accent = {
        "info": ("EAF1FA", INDIGO),
        "warn": ("F8EFE2", AMBER),
        "success": ("E8F4EF", TEAL),
    }[kind]
    table_obj = doc.add_table(rows=1, cols=1)
    table_obj.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_obj.autofit = False
    borders(table_obj, accent, 5)
    margins(table_obj, 120)
    no_split(table_obj.rows[0])
    cell = table_obj.rows[0].cells[0]
    cell.width = Cm(16.6)
    shade(cell, fill)
    para = cell.paragraphs[0]
    para.paragraph_format.space_after = Pt(0)
    para.paragraph_format.line_spacing = 1.35
    run = para.add_run(f"{title}｜")
    run.bold = True
    set_font(run, FONT, 10.5, accent)
    add_rich(para, text, 10.5, INK)
    spacer(doc, 3)


def add_code(doc, text: str) -> None:
    table_obj = doc.add_table(rows=1, cols=1)
    table_obj.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_obj.autofit = False
    borders(table_obj, "E6E1D6", 4)
    margins(table_obj, 110)
    no_split(table_obj.rows[0])
    cell = table_obj.rows[0].cells[0]
    cell.width = Cm(16.6)
    shade(cell, "F6F4EE")
    for index, line in enumerate(text.splitlines()):
        para = cell.paragraphs[0] if index == 0 else cell.add_paragraph()
        para.paragraph_format.space_after = Pt(0)
        para.paragraph_format.line_spacing = 1.15
        run = para.add_run(line)
        set_font(run, CODE_FONT, 11.0, INK)
        run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT)
    spacer(doc, 3)


def add_heading(doc, text: str, level: int, newpage: bool = True) -> None:
    para = doc.add_paragraph(style=f"Heading {level}")
    if level == 1:
        para.paragraph_format.page_break_before = newpage
    para.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    para.paragraph_format.space_after = Pt(8 if level == 1 else 4)
    para.paragraph_format.keep_with_next = True
    add_rich(para, text, {1: 21, 2: 15.5}[level], {1: "1F3A5F", 2: INDIGO}[level])
    if level == 1:
        p_pr = para._p.get_or_add_pPr()
        p_bdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "8")
        bottom.set(qn("w:space"), "4")
        bottom.set(qn("w:color"), LINE)
        p_bdr.append(bottom)
        p_pr.append(p_bdr)


def add_field(paragraph, instruction: str, placeholder: str = "1") -> None:
    begin_run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin_run._r.append(begin)

    instr_run = paragraph.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    instr_run._r.append(instr)

    sep_run = paragraph.add_run()
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    sep_run._r.append(sep)

    result = paragraph.add_run(placeholder)
    set_font(result, FONT, 9, "9AA3AF")

    end_run = paragraph.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    end_run._r.append(end)


def build_cover(doc: Document) -> None:
    section = doc.sections[0]
    section.different_first_page_header_footer = True
    doc.add_paragraph()
    band = doc.add_table(rows=1, cols=1)
    band.autofit = False
    cell = band.rows[0].cells[0]
    cell.width = Cm(16.6)
    shade(cell, INK)
    cell.paragraphs[0].add_run(" ").font.size = Pt(4)

    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(34)
    run = para.add_run("给第一次上台的同学")
    set_font(run, FONT, 10, INDIGO)
    run.bold = True

    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(12)
    run = para.add_run("零基础演示脚本")
    set_font(run, FONT, 36, INK)
    run.bold = True

    para = doc.add_paragraph()
    run = para.add_run("照着念、照着点，8 分钟完成演示")
    set_font(run, FONT, 15, TEAL)

    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(6)
    run = para.add_run("知行 · 校园智能服务助手")
    set_font(run, FONT, 18, INDIGO)

    rule = doc.add_table(rows=1, cols=1)
    rule.autofit = False
    rule_cell = rule.rows[0].cells[0]
    rule_cell.width = Cm(6)
    shade(rule_cell, "4F9D7E")
    rule_cell.paragraphs[0].add_run(" ").font.size = Pt(2)

    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(18)
    run = para.add_run("你不需要懂计算机。\n只需要会点鼠标、会打字、会按回车。")
    set_font(run, FONT, 13, "33465E")

    doc.add_paragraph().paragraph_format.space_before = Pt(30)
    meta = [
        ("适用场景", "课程演示 / 中期检查 / 结题答辩"),
        ("建议时长", "8 分钟（可压缩到 5 分钟）"),
        ("文档版本", "v1.1 · 2026 年 11 月"),
        ("团队", "嵇杨健、陈昱麒、王祥晔"),
        ("指导教师", "刘 安"),
    ]
    table_obj = doc.add_table(rows=0, cols=2)
    table_obj.autofit = False
    borders(table_obj, "E6E1D6", 4)
    margins(table_obj, 60)
    for label, value in meta:
        row = table_obj.add_row()
        no_split(row)
        left, right = row.cells
        left.width = Cm(3.4)
        right.width = Cm(13.2)
        shade(left, "F5F3EE")
        left.paragraphs[0].paragraph_format.space_after = Pt(0)
        run = left.paragraphs[0].add_run(label)
        set_font(run, FONT, 9, "75808F")
        right.paragraphs[0].paragraph_format.space_after = Pt(0)
        add_rich(right.paragraphs[0], value, 9, INK)

    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(18)
    run = para.add_run("先翻到第 2 页。")
    set_font(run, FONT, 10, AMBER)
    para.alignment = WD_ALIGN_PARAGRAPH.RIGHT


def build_docx() -> None:
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)

    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(12)
    normal.font.color.rgb = RGBColor.from_string(INK)
    normal._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(5)

    for name, size, color in (("Heading 1", 21, "1F3A5F"), ("Heading 2", 15.5, INDIGO)):
        style = doc.styles[name]
        style.font.name = FONT
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT)

    build_cover(doc)

    header = section.header
    hp = header.paragraphs[0]
    hp.paragraph_format.tab_stops.add_tab_stop(Cm(16.6), alignment=2)
    run = hp.add_run("零基础演示脚本")
    set_font(run, FONT, 8.5, "75808F")
    run = hp.add_run("\t知行 · 校园智能服务助手")
    set_font(run, FONT, 8.5, "9AA3AF")

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run("第 ")
    set_font(run, FONT, 9, "9AA3AF")
    add_field(fp, " PAGE ")
    run = fp.add_run(" 页 / 共 ")
    set_font(run, FONT, 9, "9AA3AF")
    add_field(fp, " NUMPAGES ")
    run = fp.add_run(" 页")
    set_font(run, FONT, 9, "9AA3AF")

    for block in Blocks:
        kind = block[0]
        if kind == "h1":
            add_heading(doc, block[1], 1, block[2])
        elif kind == "h2":
            add_heading(doc, block[1], 2)
        elif kind == "p":
            para = doc.add_paragraph()
            add_rich(para, block[1], 12, INK)
        elif kind == "bullets":
            for item in block[1]:
                para = doc.add_paragraph(style="List Bullet")
                para.paragraph_format.space_after = Pt(3)
                add_rich(para, item, 12, INK)
            spacer(doc, 3)
        elif kind == "table":
            add_table(doc, block[1], block[2], block[3])
        elif kind == "callout":
            add_callout(doc, block[1], block[2], block[3])
        elif kind == "code":
            add_code(doc, block[1])
        elif kind == "image":
            path = DOCS / block[1]
            if path.exists():
                doc.add_picture(str(path), width=Cm(block[3]))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                caption = doc.add_paragraph()
                caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = caption.add_run(block[2])
                set_font(run, FONT, 9, "75808F")
                caption.paragraph_format.space_after = Pt(8)
        elif kind == "pagebreak":
            doc.add_page_break()

    doc.save(OUT_DOCX)
    print("DOCX saved:", OUT_DOCX)


def build_markdown() -> None:
    lines = [
        "# 知行 · 校园智能服务助手",
        "",
        "## 零基础演示脚本",
        "",
        "> 照着念、照着点，8 分钟完成演示。",
        ">",
        "> 团队：嵇杨健、陈昱麒、王祥晔 ｜ 指导教师：刘 安 ｜ v1.1 · 2026 年 11 月",
        "",
        "---",
        "",
    ]
    for block in Blocks:
        kind = block[0]
        if kind == "h1":
            lines.extend([f"# {block[1]}", ""])
        elif kind == "h2":
            lines.extend([f"## {block[1]}", ""])
        elif kind == "p":
            lines.extend([block[1], ""])
        elif kind == "bullets":
            lines.extend([f"- {item}" for item in block[1]])
            lines.append("")
        elif kind == "table":
            headers, rows = block[1], block[2]
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
            for row in rows:
                lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
            lines.append("")
        elif kind == "callout":
            label = {"info": "提示", "warn": "注意", "success": "记住"}[block[1]]
            lines.extend([f"> **{label}｜{block[2]}**", ">", f"> {block[3]}", ""])
        elif kind == "code":
            lines.extend(["```text", block[1], "```", ""])
        elif kind == "image":
            lines.extend([f"![{block[2]}]({block[1]})", "", f"*{block[2]}*", ""])
        elif kind == "pagebreak":
            lines.extend(["---", ""])
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("Markdown saved:", OUT_MD)


if __name__ == "__main__":
    build_docx()
    build_markdown()
