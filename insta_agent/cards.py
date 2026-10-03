"""카드뉴스 이미지(1080x1350, 인스타 4:5)를 Pillow로 직접 그린다. 기사 사진은 쓰지 않는다.

구성: 표지 → 핵심 포인트(항목마다 1장) → 출처 안내. 배경은 그라데이션이며,
AI가 만든 배경 이미지가 있으면 그 위에 어두운 막을 씌워 글자가 잘 보이게 한다.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

from .content import NewsDraft

W, H = 1080, 1350
MARGIN = 84
FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]
KST = timezone(timedelta(hours=9))
NAVY_TOP, NAVY_BOTTOM = (9, 20, 44), (22, 52, 98)
WHITE, SOFT = (255, 255, 255), (178, 192, 214)
BREAKING_COLOR, NEWS_COLOR = (255, 69, 58), (64, 156, 255)


def find_font(configured: str = "") -> str:
    for path in [configured, *FONT_CANDIDATES]:
        if path and os.path.exists(path):
            return path
    raise FileNotFoundError("한글 폰트를 찾지 못했습니다. .env의 FONT_PATH에 .ttf/.ttc 경로를 지정하세요.")


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """픽셀 폭 기준 줄바꿈. 띄어쓰기 단위로 넘기되, 한 단어가 너무 길면 글자 단위로 자른다."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split(" "):
            trial = f"{current} {word}".strip()
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
                continue
            if current:
                lines.append(current)
            current = ""
            for ch in word:
                if draw.textlength(current + ch, font=font) > max_width and current:
                    lines.append(current)
                    current = ch
                else:
                    current += ch
        lines.append(current)
    return lines


def _gradient() -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        px.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(NAVY_TOP, NAVY_BOTTOM)))
    return img


def _background(bg_path: str | None) -> Image.Image:
    if not bg_path or not os.path.exists(bg_path):
        return _gradient()
    img = Image.open(bg_path).convert("RGB")
    scale = max(W / img.width, H / img.height)  # 화면을 꽉 채우도록 확대 후 중앙 자르기
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1))
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H))
    shade = Image.new("RGB", (W, H), NAVY_TOP)
    mask = Image.new("L", (W, H))
    m = ImageDraw.Draw(mask)
    for y in range(H):  # 위는 옅게, 아래로 갈수록 진하게
        m.line([(0, y), (W, y)], fill=int(150 + 85 * y / H))
    return Image.composite(shade, img, mask)


def _bold(draw, xy, text, font, fill, stroke=1):
    draw.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=fill)


def _chrome(img: Image.Image, font_path: str, page: int, total: int, label: str, color, brand: str) -> ImageDraw.ImageDraw:
    d = ImageDraw.Draw(img)
    badge = ImageFont.truetype(font_path, 36)
    tw = int(d.textlength(label, font=badge))
    d.rounded_rectangle([MARGIN, 84, MARGIN + tw + 56, 84 + 70], radius=35, fill=color)
    _bold(d, (MARGIN + 28, 94), label, badge, WHITE, 0)
    date = datetime.now(KST).strftime("%Y.%m.%d")
    small = ImageFont.truetype(font_path, 32)
    d.text((W - MARGIN - d.textlength(date, font=small), 98), date, font=small, fill=SOFT)
    d.line([(MARGIN, H - 130), (W - MARGIN, H - 130)], fill=(70, 92, 130), width=2)
    d.text((MARGIN, H - 98), brand, font=small, fill=SOFT)
    pg = f"{page} / {total}"
    d.text((W - MARGIN - d.textlength(pg, font=small), H - 98), pg, font=small, fill=SOFT)
    return d


def render_cards(
    draft: NewsDraft,
    out_dir: str,
    font_path: str = "",
    footer: str = "",
    brand: str = "",
    breaking: bool = False,
    bg_path: str | None = None,
) -> list[str]:
    """표지 + 핵심 포인트(항목당 1장) + 출처 안내. 저장한 파일 경로 목록을 순서대로 반환."""
    font = find_font(font_path)
    os.makedirs(out_dir, exist_ok=True)
    bullets = draft.bullets[:3]
    total = len(bullets) + 2
    label, color = ("속보", BREAKING_COLOR) if breaking else ("오늘의 뉴스", NEWS_COLOR)
    paths: list[str] = []

    def save(img: Image.Image, name: str) -> None:
        path = os.path.join(out_dir, name)
        img.save(path)
        paths.append(path)

    # 1) 표지
    img = _background(bg_path)
    d = _chrome(img, font, 1, total, label, color, brand)
    big = ImageFont.truetype(font, 100)
    lines = wrap_text(d, draft.headline, big, W - 2 * MARGIN)
    y = max(330, (H - len(lines) * 140) // 2 - 40)
    for line in lines[:5]:
        _bold(d, (MARGIN, y), line, big, WHITE, 2)
        y += 140
    d.rounded_rectangle([MARGIN, y + 24, MARGIN + 140, y + 32], radius=4, fill=color)
    hint = ImageFont.truetype(font, 38)
    d.text((MARGIN, H - 260), "옆으로 넘겨 핵심을 확인하세요  →", font=hint, fill=SOFT)
    save(img, "1_cover.png")

    # 2) 핵심 포인트: 항목마다 한 장
    for n, text in enumerate(bullets, 1):
        img = _background(bg_path)
        d = _chrome(img, font, n + 1, total, label, color, brand)
        num = ImageFont.truetype(font, 200)
        _bold(d, (MARGIN, 250), f"{n:02d}", num, color, 3)
        body = ImageFont.truetype(font, 70)
        y = 560
        for line in wrap_text(d, text, body, W - 2 * MARGIN)[:6]:
            _bold(d, (MARGIN, y), line, body, WHITE, 1)
            y += 108
        save(img, f"{n + 1}_point.png")

    # 3) 출처 안내
    img = _background(bg_path)
    d = _chrome(img, font, total, total, label, color, brand)
    title = ImageFont.truetype(font, 76)
    _bold(d, (MARGIN, 330), "출처 · 더 보기", title, WHITE, 2)
    host = urlparse(draft.source_link).netloc.replace("www.", "") or "원문 기사"
    sub = ImageFont.truetype(font, 48)
    d.text((MARGIN, 470), host, font=sub, fill=color)
    note = ImageFont.truetype(font, 40)
    y = 580
    for line in wrap_text(d, "자세한 내용은 원문 기사를 확인하세요. 링크는 캡션에 있습니다.", note, W - 2 * MARGIN):
        d.text((MARGIN, y), line, font=note, fill=SOFT)
        y += 62
    if footer:
        foot = ImageFont.truetype(font, 30)
        y = H - 300
        for line in wrap_text(d, footer, foot, W - 2 * MARGIN):
            d.text((MARGIN, y), line, font=foot, fill=SOFT)
            y += 46
    save(img, f"{total}_source.png")
    return paths
