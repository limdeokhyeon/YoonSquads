"""Unsplash에서 주제에 맞는 무료 사진 한 장을 찾아 카드 배경으로 저장한다.

API 이용 조건에 따라 다운로드 집계 호출을 하고, 촬영자 출처를 캡션에 남길 문구로 돌려준다.
"""

from __future__ import annotations

import requests

from .config import Config

API = "https://api.unsplash.com"
UTM = "utm_source=yoonsquads_news&utm_medium=referral"


def fetch_unsplash(cfg: Config, query: str, path: str, http=requests) -> tuple[str, str]:
    """사진을 `path`에 저장하고 (캡션에 넣을 출처 문구, 다운로드 집계 주소)를 돌려준다. 못 찾으면 예외.

    다운로드 집계는 사진을 실제로 쓰는 시점(승인)에 `track_download`로 따로 호출한다."""
    if not cfg.unsplash_key:
        raise RuntimeError("UNSPLASH_ACCESS_KEY가 없습니다")
    headers = {"Authorization": f"Client-ID {cfg.unsplash_key}", "Accept-Version": "v1"}
    resp = http.get(
        f"{API}/search/photos",
        headers=headers,
        params={"query": query or "news", "orientation": "portrait", "per_page": 10, "content_filter": "high"},
        timeout=20,
    )
    resp.raise_for_status()
    results = resp.json().get("results") or []
    if not results:
        raise RuntimeError(f"Unsplash에서 '{query}' 사진을 찾지 못했습니다")
    photo = results[0]
    sep = "&" if "?" in photo["urls"]["raw"] else "?"
    img = http.get(f"{photo['urls']['raw']}{sep}w=1080&h=1350&fit=crop&q=80", timeout=60)
    img.raise_for_status()
    with open(path, "wb") as f:
        f.write(img.content)
    user = photo["user"]
    profile = f"{user['links']['html']}?{UTM}"
    return f"{user.get('name', 'Unsplash')} / Unsplash {profile}", photo["links"]["download_location"]


def track_download(cfg: Config, download_location: str, http=requests) -> None:
    """이용 조건: 사진을 실제로 쓸 때 다운로드 집계 주소를 호출한다. 실패해도 발행은 막지 않는다."""
    try:
        http.get(download_location, headers={"Authorization": f"Client-ID {cfg.unsplash_key}", "Accept-Version": "v1"}, timeout=20)
    except Exception as e:
        print(f"unsplash track error: {e}")
