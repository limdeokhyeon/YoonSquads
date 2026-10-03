"""한 장짜리 뉴스 카드(1080x1350, 인스타 4:5)를 그린다.

사진(AI 배경)을 화면 가득 깔고, 아래쪽을 어둡게 덮은 뒤
[배지] [작은 문구] 큰 제목 / 부제 / "출처: 언론사 | 날짜" 순으로 아래에서부터 쌓는다.
배경이 없으면 남색 그라데이션을 쓴다. 기사 사진은 쓰지 않는다.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

from .content import NewsDraft

W, H = 1080, 1350
MARGIN = 72
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
WHITE, SOFT, DIM = (255, 255, 255), (222, 226, 234), (160, 168, 184)
BADGE_RED = (214, 24, 24)
NAVY_TOP, NAVY_BOTTOM = (9, 20, 44), (22, 52, 98)


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


def _fit(draw, text: str, font_path: str, max_w: int, max_lines: int, start: int, minimum: int):
    """글자 크기를 줄여 가며 max_lines 안에 들어가는 크기를 찾는다. 그래도 넘치면 마지막 줄을 …로 자른다."""
    for size in range(start, minimum - 1, -4):
        font = ImageFont.truetype(font_path, size)
        lines = wrap_text(draw, text, font, max_w)
        if len(lines) <= max_lines:
            return font, lines
    lines = lines[:max_lines]
    while lines and draw.textlength(lines[-1] + "…", font=font) > max_w:
        lines[-1] = lines[-1][:-1]
    lines[-1] += "…"
    return font, lines


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
    scale = max(W / img.width, H / img.height)  # 화면을 꽉 채우도록 확대
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1))
    left = (img.width - W) // 2
    top = int((img.height - H) * 0.25)  # 피사체가 위쪽에 있으니 위를 더 남기고 아래를 자른다
    return img.crop((left, top, left + W, top + H))


def _shade(img: Image.Image) -> Image.Image:
    """위는 그대로 두고 40% 지점부터 서서히 어두워져, 아래쪽 글자가 잘 보이게 한다."""
    mask = Image.new("L", (W, H))
    m = ImageDraw.Draw(mask)
    for y in range(H):
        t = min(max((y / H - 0.38) / 0.42, 0.0), 1.0)
        t = t * t * (3 - 2 * t)  # smoothstep
        m.line([(0, y), (W, y)], fill=int(245 * t))
    return Image.composite(Image.new("RGB", (W, H), (4, 6, 12)), img, mask)


def _bold(draw, xy, text, font, fill, stroke=1):
    draw.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=fill)


def render_card(
    draft: NewsDraft,
    out_dir: str,
    font_path: str = "",
    bg_path: str | None = None,
    ai_label: bool = False,
    breaking: bool = False,
) -> str:
    """카드 한 장을 저장하고 경로를 돌려준다."""
    font_file = find_font(font_path)
    os.makedirs(out_dir, exist_ok=True)
    img = _shade(_background(bg_path))
    d = ImageDraw.Draw(img)
    max_w = W - 2 * MARGIN

    head_font, head_lines = _fit(d, draft.headline, font_file, max_w, 3, 112, 76)
    sub_font, sub_lines = _fit(d, draft.subhead, font_file, max_w, 2, 50, 36) if draft.subhead else (None, [])
    kick_font = ImageFont.truetype(font_file, 54)
    badge_text = draft.badge or ("속보" if breaking else "뉴스")
    badge_font = ImageFont.truetype(font_file, 58)
    foot_font = ImageFont.truetype(font_file, 32)
    date = datetime.now(KST).strftime("%Y.%m.%d.")
    footer = f"출처: {draft.source_name or '기사 원문'}  |  {date}"

    # 아래에서 위로 쌓는다
    y = H - 64 - 36
    d.text((MARGIN, y), footer, font=foot_font, fill=DIM)
    y -= 36
    if sub_lines:
        sub_h = int(sub_font.size * 1.36)
        y -= len(sub_lines) * sub_h
        for i, line in enumerate(sub_lines):
            d.text((MARGIN, y + i * sub_h), line, font=sub_font, fill=SOFT)
        y -= 22
    line_h = int(head_font.size * 1.24)
    y -= len(head_lines) * line_h
    for i, line in enumerate(head_lines):
        _bold(d, (MARGIN, y + i * line_h), line, head_font, WHITE, 2)
    y -= 14
    if draft.kicker:
        y -= 74
        _bold(d, (MARGIN, y), draft.kicker, kick_font, SOFT, 1)
        y -= 6
    bw = int(d.textlength(badge_text, font=badge_font)) + 56
    y -= 96
    d.rounded_rectangle([MARGIN, y, MARGIN + bw, y + 84], radius=6, fill=BADGE_RED)
    _bold(d, (MARGIN + 28, y + 8), badge_text, badge_font, WHITE, 1)

    if ai_label and bg_path:
        tag_font = ImageFont.truetype(font_file, 26)
        tw = int(d.textlength("AI 생성 이미지", font=tag_font))
        d.rounded_rectangle([W - MARGIN - tw - 36, 48, W - MARGIN, 48 + 46], radius=23, fill=(0, 0, 0))
        d.text((W - MARGIN - tw - 18, 55), "AI 생성 이미지", font=tag_font, fill=SOFT)

    path = os.path.join(out_dir, "card.png")
    img.save(path)
    return path
