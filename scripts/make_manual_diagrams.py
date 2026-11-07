"""生成演示手册用的两张架构示意图。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
INK = "#18263A"
MUTED = "#75808F"
LINE = "#D8D2C4"
PAPER = "#FCFBF8"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """加载微软雅黑。"""
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def center_text(draw: ImageDraw.ImageDraw, box, text: str, size: int, color: str = INK, bold: bool = False) -> None:
    """在矩形内居中绘制单行文本。"""
    x0, y0, x1, y1 = box
    draw.text(((x0 + x1) / 2, (y0 + y1) / 2), text, font=font(size, bold), fill=color, anchor="mm")


def rounded(draw, box, fill, outline=LINE, radius=18, width=2) -> None:
    """绘制圆角矩形。"""
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def arrow(draw, start, end, color="#4F7FBF", width=3) -> None:
    """绘制带箭头的连线。"""
    draw.line([start, end], fill=color, width=width)
    x, y = end
    sx, sy = start
    if abs(x - sx) >= abs(y - sy):
        direction = 1 if x > sx else -1
        points = [(x, y), (x - 12 * direction, y - 7), (x - 12 * direction, y + 7)]
    else:
        direction = 1 if y > sy else -1
        points = [(x, y), (x - 7, y - 12 * direction), (x + 7, y - 12 * direction)]
    draw.polygon(points, fill=color)


def build_architecture() -> None:
    """六层解耦架构图。"""
    width, height = 1600, 900
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)

    draw.text((60, 34), "六层解耦：能力下沉到平台侧", font=font(42, True), fill=INK)
    draw.text(
        (60, 88),
        "Agent 应用层只做路由与业务语义；检索、编排、工具调用由平台能力层托管",
        font=font(24),
        fill=MUTED,
    )

    layers = [
        ("用户与渠道层", "校园门户 Web  ·  企业微信 / 公众号  ·  小程序 / H5  ·  自助终端", "#EAF1FA"),
        ("接入与网关层", "REST API  ·  统一错误结构  ·  CORS  ·  日志审计", "#E8F4EF"),
        ("Agent 应用层", "意图识别与路由  ·  知识问答 Agent  ·  办事流程 Agent  ·  兜底转人工", "#F8EFE2"),
        ("平台能力层", "混合检索  ·  工作流引擎  ·  工具 / MCP  ·  记忆变量  ·  Mock 模型", "#EAF1FA"),
        ("数据与知识层", "12 篇制度  ·  60 个分块  ·  会话 / 工单 JSON  ·  审计 JSONL", "#E8F4EF"),
        ("基础设施层", "Python + FastAPI  ·  本地文件存储  ·  可替换华为云 ECS / OBS / MaaS", "#F2F0EA"),
    ]
    top = 135
    band_h = 104
    gap = 14
    for index, (label, content, fill) in enumerate(layers):
        y = top + index * (band_h + gap)
        draw.rounded_rectangle((60, y, 1540, y + band_h), radius=14, fill=fill, outline=LINE, width=2)
        draw.rounded_rectangle((60, y, 300, y + band_h), radius=14, fill="#FFFFFF", outline=LINE, width=2)
        center_text(draw, (60, y, 300, y + band_h), label, 24, INK, True)
        draw.text((330, y + band_h / 2), content, font=font(24), fill="#33465E", anchor="lm")

    draw.text(
        (60, 845),
        "安全与合规：引用校验 · 拒答边界 · 幂等 · 人工确认 · 全程留痕",
        font=font(22),
        fill="#2F5F9E",
    )
    image.save(OUT / "architecture-six-layers.png")


def build_dual_agent() -> None:
    """双 Agent 分工与数据流图。"""
    width, height = 1400, 720
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)

    draw.text((60, 32), "双 Agent 分工：问答保依据，办事保确定性", font=font(38, True), fill=INK)
    draw.text((60, 82), "同一入口，按意图路由到两个 Agent；失败统一兜底转人工", font=font(22), fill=MUTED)

    user_box = (560, 125, 840, 185)
    router_box = (520, 230, 880, 290)
    qa_box = (170, 350, 560, 420)
    wf_box = (840, 350, 1230, 420)
    qa_detail = (150, 465, 580, 565)
    wf_detail = (820, 465, 1250, 565)
    audit_box = (340, 620, 1060, 675)

    for box, text, fill, color in (
        (user_box, "用户输入", "#FFFFFF", INK),
        (router_box, "意图识别与路由", "#EAF1FA", "#2F5F9E"),
        (qa_box, "知识问答 Agent", "#EAF1FA", "#2F5F9E"),
        (wf_box, "办事流程 Agent", "#E8F4EF", "#357A5F"),
    ):
        rounded(draw, box, fill, outline=color, width=2)
        center_text(draw, box, text, 28, color, True)

    rounded(draw, qa_detail, "#F7FAFE")
    draw.multiline_text(
        (185, 490),
        "混合检索 → 引用校验 → 带依据回答\n低置信度改写；仍不足则拒答转人工",
        font=font(22),
        fill="#33465E",
        spacing=14,
    )
    rounded(draw, wf_detail, "#F5FBF8")
    draw.multiline_text(
        (855, 490),
        "工作流 → 工具调用 → 人工确认 → 回执\n重试 1 次；仍失败转人工并保留上下文",
        font=font(22),
        fill="#33465E",
        spacing=14,
    )

    rounded(draw, audit_box, "#F8EFE2", outline="#BD8548", width=2)
    center_text(draw, audit_box, "审计留痕：消息 · 意图 · 检索 · 工具 · 节点 · 确认 · 可回放", 20, "#8A5A24", True)

    arrow(draw, (700, 185), (700, 230))
    arrow(draw, (700, 290), (430, 350))
    arrow(draw, (700, 290), (970, 350))
    arrow(draw, (365, 420), (365, 465))
    arrow(draw, (1035, 420), (1035, 465))
    arrow(draw, (365, 565), (560, 620), color="#BD8548")
    arrow(draw, (1035, 565), (840, 620), color="#BD8548")

    image.save(OUT / "dual-agent-flow.png")


if __name__ == "__main__":
    build_architecture()
    build_dual_agent()
    print("diagrams saved:", OUT)
