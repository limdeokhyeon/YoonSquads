"""Unsplash에서 주제에 맞는 무료 사진 한 장을 찾아 카드 배경으로 저장한다.

API 이용 조건에 따라 다운로드 집계 호출을 하고, 촬영자 출처를 캡션에 남길 문구로 돌려준다.
"""

from __future__ import annotations

import random

import requests

from .config import Config
from .log import log
from .safety import redact

API = "https://api.unsplash.com"
UTM = "utm_source=yoonsquads_news&utm_medium=referral"


def _search(cfg: Config, headers: dict, query: str, portrait: bool, http) -> list[dict]:
    params = {"query": query, "per_page": 30, "content_filter": "high"}
    if portrait:
        params["orientation"] = "portrait"
    resp = http.get(f"{API}/search/photos", headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json().get("results") or []


def _attempts(query: str) -> list[tuple[str, bool]]:
    """사진을 못 찾을 때를 대비한 검색 순서: 원래 키워드(세로→아무 방향) → 앞 두 단어 → 첫 단어. 최대 4번."""
    words = (query or "news").split()[:5]
    out = [(" ".join(words), True), (" ".join(words), False)]
    if len(words) > 2:
        out.append((" ".join(words[:2]), False))
    if len(words) > 1:
        out.append((words[0], False))
    return out


TOP_N = 10  # 검색 결과 상위 몇 장 중에서 무작위로 고를지


def fetch_unsplash(
    cfg: Config, query: str, path: str, http=requests, exclude: set[str] | None = None,
    extra_queries: list[str] | None = None, rng=random,
) -> tuple[str, str, str]:
    """사진을 `path`에 저장하고 (캡션에 넣을 출처 문구, 다운로드 집계 주소, 사진 ID)를 돌려준다. 끝내 못 찾으면 예외.

    `query`와 `extra_queries`를 차례로 시도해 처음 쓸 만한 사진이 나온 검색어에서 고른다.
    `exclude`(최근 쓴 사진 ID)는 건너뛰고, 남은 상위 결과 중 무작위로 한 장을 고른다.
    제외하고 나면 하나도 안 남는 경우에만 제외 없이 고른다(사진이 없어 실패하느니 반복이 낫다).
    다운로드 집계는 사진을 실제로 쓰는 시점(승인)에 `track_download`로 따로 호출한다.
    가로 사진도 카드 비율(1080x1350)로 잘라서 쓴다."""
    if not cfg.unsplash_key:
        raise RuntimeError("UNSPLASH_ACCESS_KEY가 없습니다")
    headers = {"Authorization": f"Client-ID {cfg.unsplash_key}", "Accept-Version": "v1"}
    exclude = exclude or set()
    queries = [q for q in dict.fromkeys([query, *(extra_queries or [])]) if q and q.strip()] or ["news"]
    photo = None
    fallback = None  # 전부 최근에 쓴 사진뿐일 때를 위한 대비책
    for base in queries:
        for q, portrait in _attempts(base):
            results = _search(cfg, headers, q, portrait, http)
            fresh = [r for r in results if r.get("id") not in exclude]
            if fresh:
                photo = rng.choice(fresh[:TOP_N])
                break
            if results and fallback is None:
                fallback = rng.choice(results[:TOP_N])
        if photo is not None:
            break
    photo = photo or fallback
    if photo is None:
        raise RuntimeError(f"Unsplash에서 '{query}' 사진을 찾지 못했습니다")
    sep = "&" if "?" in photo["urls"]["raw"] else "?"
    img = http.get(f"{photo['urls']['raw']}{sep}w=1080&h=1350&fit=crop&q=80", timeout=60)
    img.raise_for_status()
    with open(path, "wb") as f:
        f.write(img.content)
    user = photo["user"]
    profile = f"{user['links']['html']}?{UTM}"
    return f"{user.get('name', 'Unsplash')} / Unsplash {profile}", photo["links"]["download_location"], str(photo.get("id", ""))


def track_download(cfg: Config, download_location: str, http=requests) -> None:
    """이용 조건: 사진을 실제로 쓸 때 다운로드 집계 주소를 호출한다. 실패해도 발행은 막지 않는다."""
    try:
        http.get(download_location, headers={"Authorization": f"Client-ID {cfg.unsplash_key}", "Accept-Version": "v1"}, timeout=20)
    except Exception as e:
        log.warning(f"unsplash track error: {redact(e)}")
