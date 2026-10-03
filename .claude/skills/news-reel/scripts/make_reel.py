#!/usr/bin/env python3
"""속보 릴스(1080x1920 mp4) 생성기.

위쪽: 사용자가 준 사진(글자 부분 제외), 아래쪽: 검은 배경 + 태그/제목/보조문구/출처.
예)
  make_reel.py --photo in.png --photo-bottom 765 \
    --tag "속보" --pre "합참 발표" \
    --lines "北, 동해상으로" "탄도미사일 발사" "700km 이상 비행" \
    --post "연 5% · 30년 기준" --source "KBS | 2026.10.03." --out out.mp4
"""
import argparse, os, subprocess, sys, tempfile, urllib.request
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fonts")
FONTS = {
    "bold": "https://cdn.jsdelivr.net/gh/fonts-archive/NanumGothic/NanumGothicExtraBold.ttf",
    "reg": "https://cdn.jsdelivr.net/gh/fonts-archive/NanumGothic/NanumGothic.ttf",
}


def font(kind, size):
    path = os.path.join(FONT_DIR, kind + ".ttf")
    if not os.path.exists(path):
        os.makedirs(FONT_DIR, exist_ok=True)
        urllib.request.urlretrieve(FONTS[kind], path)
    return ImageFont.truetype(path, size)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--photo", required=True)
    a.add_argument("--photo-bottom", type=int, required=True,
                   help="원본 사진에서 글자/태그가 시작되기 전까지의 y(px). 이 위쪽만 사용")
    a.add_argument("--photo-x", type=float, default=0.5, help="가로 자르기 위치 0(왼쪽)~1(오른쪽)")
    a.add_argument("--tag", default="속보")
    a.add_argument("--pre", help="제목 위 작은 한 줄 (예: 합참 발표)")
    a.add_argument("--lines", nargs="+", required=True, help="제목(2~4줄)")
    a.add_argument("--post", nargs="*", default=[], help="제목 아래 보조 문구(줄별)")
    a.add_argument("--source", required=True, help="예: KBS | 2026.10.03.")
    a.add_argument("--seconds", type=int, default=10)
    a.add_argument("--out", required=True)
    a.add_argument("--preview", help="첫 프레임을 PNG로도 저장할 경로")
    o = a.parse_args()

    photo_h = 800
    src = Image.open(o.photo).convert("RGB").crop((0, 0, Image.open(o.photo).width, o.photo_bottom))
    s = photo_h / src.height
    ph = src.resize((int(src.width * s), photo_h), Image.LANCZOS)
    if ph.width < W:                       # 가로가 모자라면 폭 기준으로 다시 확대
        s = W / src.width
        ph = src.resize((W, int(src.height * s)), Image.LANCZOS)
        photo_h = ph.height
    x0 = int((ph.width - W) * o.photo_x)
    ph = ph.crop((x0, 0, x0 + W, photo_h))

    im = Image.new("RGB", (W, H), (0, 0, 0))
    im.paste(ph, (0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    fade = 280
    for y in range(photo_h - fade, photo_h):
        d.line((0, y, W, y), fill=(0, 0, 0, int(255 * ((y - (photo_h - fade)) / fade) ** 1.1)))

    y = photo_h + 50
    tf = font("bold", 50)
    tw = int(d.textlength(o.tag, font=tf)) + 40
    d.rounded_rectangle((70, y, 70 + tw, y + 70), 8, fill=(230, 25, 25))
    d.text((90, y + 4), o.tag, font=tf, fill=(255, 255, 255))
    y += 100
    if o.pre:
        d.text((70, y), o.pre, font=font("reg", 44), fill=(225, 225, 225))
        y += 65
    size = 92
    while max(d.textlength(l, font=font("bold", size)) for l in o.lines) > 940:
        size -= 2
    for l in o.lines:
        d.text((70, y), l, font=font("bold", size), fill=(255, 255, 255))
        y += int(size * 1.23)
    y += 15
    for l in o.post:
        sz = 42
        while d.textlength(l, font=font("reg", sz)) > 940:
            sz -= 2
        d.text((70, y), l, font=font("reg", sz), fill=(225, 225, 225))
        y += int(sz * 1.35)
    y += 25
    d.text((70, y), "출처: " + o.source, font=font("reg", 34), fill=(190, 190, 190))
    if y + 60 > 1520:
        print(f"경고: 글자가 y={y+60}까지 내려가 인스타 하단 UI에 가릴 수 있음", file=sys.stderr)

    if o.preview:
        im.save(o.preview)
    with tempfile.TemporaryDirectory() as t:
        im.save(os.path.join(t, "f.png"))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS),
                        "-t", str(o.seconds), "-i", os.path.join(t, "f.png"),
                        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac",
                        "-movflags", "+faststart", o.out], check=True)
    print("saved", o.out)


if __name__ == "__main__":
    main()
