"""카드뉴스 이미지(1080x1080)를 Pillow로 직접 그린다. 기사 사진은 쓰지 않는다."""

from __future__ import annotations

import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

from .content import NewsDraft

SIZE = 1080
FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]
BG, ACCENT, FG, SUB = "#FFF6EE", "#FF7A59", "#2B2B2B", "#8A7F78"


def find_font(configured: str = "") -> str:
    for path in [configured, *FONT_CANDIDATES]:
        if path and os.path.exists(path):
            return path
    raise FileNotFoundError("한글 폰트를 찾지 못했습니다. .env의 FONT_PATH에 .ttf/.ttc 경로를 지정하세요.")


def _wrap(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width=width)) or text


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, SIZE, 24], fill=ACCENT)
    return img, d


def render_cards(draft: NewsDraft, out_dir: str, font_path: str = "", footer: str = "") -> list[str]:
    """표지 1장 + 본문 1장. 저장한 파일 경로 목록을 반환."""
    font = find_font(font_path)
    os.makedirs(out_dir, exist_ok=True)

    img, d = _canvas()
    d.text((80, 120), "오늘의 뉴스", font=ImageFont.truetype(font, 44), fill=ACCENT)
    d.multiline_text((80, 300), _wrap(draft.headline, 12), font=ImageFont.truetype(font, 88), fill=FG, spacing=24)
    cover = os.path.join(out_dir, "1_cover.png")
    img.save(cover)

    img, d = _canvas()
    d.text((80, 100), "핵심 정리", font=ImageFont.truetype(font, 52), fill=ACCENT)
    f, y = ImageFont.truetype(font, 46), 240
    for n, b in enumerate(draft.bullets, 1):
        text = _wrap(b, 18)
        d.text((80, y), f"{n}", font=f, fill=ACCENT)
        d.multiline_text((140, y), text, font=f, fill=FG, spacing=14)
        y += 70 * (text.count("\n") + 1) + 70
    if footer:
        d.text((80, SIZE - 100), footer, font=ImageFont.truetype(font, 26), fill=SUB)
    body = os.path.join(out_dir, "2_body.png")
    img.save(body)
    return [cover, body]
