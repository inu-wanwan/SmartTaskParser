"""
リッチメニューの画像（2500x843, 左右2ボタン）を作るスクリプト。

画像はリポジトリに rich_menu.png としてコミット済みなので、普段は実行不要。
デザインを変えるときだけ使う（Pillow と Noto Sans CJK が必要）:
    pip install pillow
    python tools/line_rich_menu/make_image.py [フォントのパス]
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 2500, 843
HALF = WIDTH // 2
OUT = Path(__file__).with_name("rich_menu.png")

BG_LEFT = (255, 244, 230)
BG_RIGHT = (236, 244, 252)
ACCENT_LEFT = (232, 112, 32)
ACCENT_RIGHT = (40, 110, 190)
INK = (40, 40, 40)
SUB = (110, 110, 110)
DIVIDER = (220, 220, 220)

DEFAULT_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    # ttc の index 0 が日本語（JP）
    return ImageFont.truetype(path, size, index=0)


def draw_clock(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color) -> None:
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=22)
    # 短針（10時）と長針（12時）
    for angle, length in ((-60, 0.5), (0, 0.72)):
        rad = math.radians(angle - 90)
        d.line([cx, cy, cx + r * length * math.cos(rad), cy + r * length * math.sin(rad)], fill=color, width=22)
    d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=color)


def draw_list(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color) -> None:
    for i in (-1, 0, 1):
        y = cy + i * r * 0.62
        d.ellipse([cx - r, y - 18, cx - r + 36, y + 18], fill=color)
        d.rounded_rectangle([cx - r + 70, y - 14, cx + r, y + 14], radius=14, fill=color)


def draw_label(d, center_x: int, title: str, sub: str, path: str) -> None:
    title_font = font(path, 128)
    sub_font = font(path, 64)
    d.text((center_x, 600), title, font=title_font, fill=INK, anchor="mm")
    d.text((center_x, 735), sub, font=sub_font, fill=SUB, anchor="mm")


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FONT
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_LEFT)
    d = ImageDraw.Draw(img)
    d.rectangle([HALF, 0, WIDTH, HEIGHT], fill=BG_RIGHT)
    d.line([HALF, 60, HALF, HEIGHT - 60], fill=DIVIDER, width=6)

    draw_clock(d, HALF // 2, 290, 170, ACCENT_LEFT)
    draw_label(d, HALF // 2, "リマインド", "次の1通をリマインドに", path)

    draw_list(d, HALF + HALF // 2, 290, 170, ACCENT_RIGHT)
    draw_label(d, HALF + HALF // 2, "一覧・取消", "今後24時間の予定", path)

    img.save(OUT, optimize=True)
    print(f"saved: {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
