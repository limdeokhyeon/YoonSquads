"""네이버 검색 API(뉴스)로 기사 메타데이터(제목·요약·링크)만 수집한다.

본문은 가져오지 않는다. 저작권 때문에 제목과 검색 요약만 참고해 새로 쓴다.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from dataclasses import asdict, dataclass

import requests

from .config import Config

# 2026-07 이후 신규 키는 NAVER API HUB(네이버 클라우드 플랫폼)에서 발급되며 주소·헤더가 다르다.
URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"


@dataclass
class NewsItem:
    title: str
    summary: str
    link: str
    pub_date: str

    def to_dict(self) -> dict:
        return asdict(self)


def clean(text: str) -> str:
    return html.unescape(re.sub(r"</?b>", "", text)).strip()


def search_news(cfg: Config, keyword: str, limit: int = 30, http=requests) -> list[NewsItem]:
    resp = http.get(
        URL,
        headers={"X-NCP-APIGW-API-KEY-ID": cfg.naver_client_id, "X-NCP-APIGW-API-KEY": cfg.naver_client_secret},
        params={"query": keyword, "display": limit, "sort": "date"},
        timeout=15,
    )
    resp.raise_for_status()
    return [
        NewsItem(clean(i["title"]), clean(i.get("description", "")), i.get("link") or i["originallink"], i.get("pubDate", ""))
        for i in resp.json().get("items", [])
    ]


def collect(cfg: Config, seen: set[str], http=requests) -> list[NewsItem]:
    """키워드별 최신 기사에서 아직 처리하지 않은 것을 번갈아 골라 daily_count개 반환."""
    # 본문 어딘가에만 키워드가 있는 기사는 제외: 제목이나 요약에 키워드가 있어야 한다
    pools = [
        [i for i in search_news(cfg, k, http=http) if i.link not in seen and (k in i.title or k in i.summary)]
        for k in cfg.news_keywords
    ]
    picked, titles = [], set()
    while len(picked) < cfg.daily_count and any(pools):
        for pool in pools:
            while pool:
                item = pool.pop(0)
                if item.title not in titles:  # 같은 제목 중복 제거
                    titles.add(item.title)
                    picked.append(item)
                    break
            if len(picked) >= cfg.daily_count:
                break
    return picked


def _norm(title: str) -> str:
    return re.sub(r"[\[\]()\"'“”‘’…·,.!?]|속보|단독", "", title).replace(" ", "")


def is_similar(title: str, others: list[str], threshold: float = 0.55) -> bool:
    """같은 사건을 다룬 다른 언론사 기사인지(제목이 비슷한지) 판단."""
    a = _norm(title)
    return any(SequenceMatcher(None, a, _norm(o)).ratio() >= threshold for o in others if o)


def collect_breaking(cfg: Config, seen: set[str], recent_titles: list[str], limit: int, now: datetime | None = None, http=requests) -> list[NewsItem]:
    """최근 `breaking_max_age_min`분 안에 나온 '속보' 기사 중 새 사건만 최대 limit건."""
    now = now or datetime.now(timezone.utc)
    oldest = now - timedelta(minutes=cfg.breaking_max_age_min)
    picked: list[NewsItem] = []
    titles = list(recent_titles)
    for kw in cfg.breaking_keywords:
        for item in search_news(cfg, kw, http=http):
            if len(picked) >= limit:
                return picked
            if item.link in seen or kw not in item.title:
                continue
            try:
                if parsedate_to_datetime(item.pub_date) < oldest:
                    continue
            except Exception:
                continue  # 시각을 모르면 오래된 기사일 수 있으니 제외
            if is_similar(item.title, titles):
                continue
            picked.append(item)
            titles.append(item.title)
    return picked
