"""네이버 검색 API(뉴스)로 기사 메타데이터(제목·요약·링크)만 수집한다.

본문은 가져오지 않는다. 저작권 때문에 제목과 검색 요약만 참고해 새로 쓴다.
"""

from __future__ import annotations

import html
import re
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


def search_news(cfg: Config, keyword: str, limit: int = 10, http=requests) -> list[NewsItem]:
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
    pools = [[i for i in search_news(cfg, k, http=http) if i.link not in seen] for k in cfg.news_keywords]
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
