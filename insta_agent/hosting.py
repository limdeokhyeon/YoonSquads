"""Graph API는 공개 URL만 받으므로, 카드 이미지를 imgbb에 올려 URL을 얻는다."""

from __future__ import annotations

import base64

import requests

from .config import Config


JPEG_MAGIC = b"\xff\xd8\xff"


def upload_image(cfg: Config, path: str, http=requests) -> str:
    if not cfg.imgbb_key:
        raise RuntimeError("IMGBB_API_KEY가 필요합니다 (https://api.imgbb.com 에서 무료 발급)")
    with open(path, "rb") as f:
        raw = f.read()
    if not raw.startswith(JPEG_MAGIC):  # 인스타그램은 JPEG만 받으므로 올리기 전에 막는다
        raise RuntimeError(f"JPEG 이미지가 아닙니다({path}). 인스타그램은 JPEG만 지원합니다")
    payload = base64.b64encode(raw).decode()
    resp = http.post(
        "https://api.imgbb.com/1/upload", data={"key": cfg.imgbb_key, "image": payload}, timeout=60
    )
    resp.raise_for_status()
    return resp.json()["data"]["url"]
