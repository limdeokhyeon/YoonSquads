"""OpenAI 이미지 API로 카드뉴스 배경(글자 없는 추상 이미지)을 만든다.

한글 글자는 AI가 자주 깨뜨리므로 이미지에는 글자를 넣지 않고, 글자는 cards.py가 위에 올린다.
실제 인물·얼굴·기사 사진을 흉내 내지 않도록 프롬프트에 제한을 붙인다.
"""

from __future__ import annotations

import base64

import requests

from .config import Config

GUARD = (
    " Editorial abstract illustration, symbolic and minimal, dark navy and blue palette with one warm accent, "
    "vertical composition with calm empty space. No text, no letters, no numbers, no logos, "
    "no real people, no faces, no photorealistic depiction of any real person or event."
)
DEFAULT_PROMPT = "Abstract layered geometric shapes suggesting news and information flow."


def generate_background(cfg: Config, prompt: str, path: str, http=requests) -> str:
    """배경 이미지를 `path`에 저장하고 경로를 돌려준다. 실패하면 예외를 던진다."""
    if not cfg.openai_key:
        raise RuntimeError("OPENAI_API_KEY가 없습니다")
    resp = http.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {cfg.openai_key}"},
        json={"model": cfg.openai_image_model, "prompt": (prompt or DEFAULT_PROMPT) + GUARD, "size": "1024x1536", "n": 1},
        timeout=180,
    )
    resp.raise_for_status()
    item = resp.json()["data"][0]
    if item.get("b64_json"):
        raw = base64.b64decode(item["b64_json"])
    else:
        img = http.get(item["url"], timeout=60)
        img.raise_for_status()
        raw = img.content
    with open(path, "wb") as f:
        f.write(raw)
    return path
