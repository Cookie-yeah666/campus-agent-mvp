"""把历史截图左上角的旧品牌替换为「知行」。

截图只用于文档示意；运行中的应用以 static/ 下的实时页面为准。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "docs" / "screenshots"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
FONT = "C:/Windows/Fonts/msyh.ttc"


def rebrand(path: Path) -> None:
    image = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(image)
    # 侧边栏底色（截图左上角），保持与各主题一致
    background = image.getpixel((8, 8))
    draw.rectangle((70, 26, 245, 88), fill=background)
    draw.text((78, 30), "知行", font=ImageFont.truetype(FONT_BOLD, 23), fill="#f4f7fb")
    draw.text(
        (79, 65),
        "ZHIXING COPILOT",
        font=ImageFont.truetype(FONT, 8),
        fill="#8fa0b5",
    )
    image.save(path)


if __name__ == "__main__":
    for name in (
        "01-chat.png",
        "02-chat-qa.png",
        "03-workorders.png",
        "04-audit.png",
        "05-knowledge.png",
        "06-evaluation.png",
        "07-system.png",
        "08-dark.png",
    ):
        target = SHOTS / name
        if target.exists():
            rebrand(target)
            print("rebranded", target.name)
