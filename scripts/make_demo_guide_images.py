"""为零基础演示脚本生成带标注的界面图。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "docs" / "screenshots"
OUT = ROOT / "docs" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

FONT = "C:/Windows/Fonts/msyhbd.ttc"
RED = "#C0564F"


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, size)


def circle(draw: ImageDraw.ImageDraw, x: int, y: int, number: str, radius: int = 24) -> None:
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=RED, outline="white", width=4)
    draw.text((x, y - 2), number, font=font(28), fill="white", anchor="mm")


def box(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], width: int = 5) -> None:
    draw.rounded_rectangle(rect, radius=12, outline=RED, width=width)


def make_map() -> None:
    image = Image.open(SHOTS / "01-chat.png").convert("RGB")
    draw = ImageDraw.Draw(image)
    box(draw, (12, 88, 258, 132))            # 新建对话
    box(draw, (366, 866, 1152, 962))         # 输入框
    box(draw, (1064, 894, 1146, 950))        # 发送
    box(draw, (1246, 68, 1598, 992), 3)      # 执行轨迹
    box(draw, (452, 724, 552, 762))          # 确认提交
    circle(draw, 250, 92, "1")
    circle(draw, 250, 157, "2")
    circle(draw, 250, 470, "3")
    circle(draw, 386, 876, "4")
    circle(draw, 1135, 902, "5")
    circle(draw, 1420, 110, "6")
    image.save(OUT / "ui-map.png")


def make_card_crop() -> None:
    image = Image.open(SHOTS / "01-chat.png").convert("RGB")
    crop = image.crop((420, 520, 810, 870)).resize((780, 700), Image.LANCZOS)
    draw = ImageDraw.Draw(crop)
    # 确认提交按钮在裁剪图中的位置
    rect = (64, 408, 264, 484)
    box(draw, rect, 6)
    draw.line((560, 330, 210, 446), fill=RED, width=6)
    draw.polygon([(210, 446), (240, 432), (232, 462)], fill=RED)
    draw.rounded_rectangle((500, 235, 740, 295), radius=12, fill="white", outline=RED, width=4)
    draw.text((620, 265), "点这里", font=font(30), fill=RED, anchor="mm")
    crop.save(OUT / "ui-card.png")


def make_workorder_crop() -> None:
    image = Image.open(SHOTS / "03-workorders.png").convert("RGB")
    crop = image.crop((300, 230, 1250, 700))
    crop.save(OUT / "ui-workorder.png")


def make_citation_crop() -> None:
    image = Image.open(SHOTS / "02-chat-qa.png").convert("RGB")
    crop = image.crop((405, 90, 820, 330)).resize((830, 480), Image.LANCZOS)
    draw = ImageDraw.Draw(crop)
    box(draw, (44, 30, 800, 420), 6)
    draw.rounded_rectangle((480, 430, 790, 468), radius=10, fill="white", outline=RED, width=3)
    draw.text((635, 449), "红框里就是出处", font=font(24), fill=RED, anchor="mm")
    crop.save(OUT / "ui-citation.png")


if __name__ == "__main__":
    make_map()
    make_card_crop()
    make_citation_crop()
    make_workorder_crop()
    print("guide images saved:", OUT)
