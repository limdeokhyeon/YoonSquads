"""기사 본문 앞부분을 사실 파악용으로만 읽어 온다. 결과물에 그대로 옮기지 않는다.

robots.txt가 막은 주소, 접속 실패, 본문을 못 찾은 경우는 빈 문자열을 돌려주고
호출한 쪽은 제목·요약만으로 진행한다.
"""
from __future__ import annotations

import time
import urllib.robotparser
from difflib import SequenceMatcher
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

UA = "YoonSquadsNewsBot/1.0 (personal summarizer; human-reviewed)"
MAX_CHARS = 2000
SELECTORS = ["#dic_area", "#newsct_article", "#articeBody", "#articleBodyContents", "article"]
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def allowed(url: str, http=requests) -> bool:
    host = urlparse(url)
    root = f"{host.scheme}://{host.netloc}"
    if root not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            resp = http.get(f"{root}/robots.txt", headers={"User-Agent": UA}, timeout=10)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
                _robots[root] = rp
            else:  # robots.txt 없음 = 제한 없음
                _robots[root] = None
        except Exception:
            return False  # 확인하지 못하면 읽지 않는다
    rp = _robots[root]
    return True if rp is None else rp.can_fetch(UA, url)


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "figure", "aside", "header", "footer"]):
        tag.decompose()
    for sel in SELECTORS:
        node = soup.select_one(sel)
        if node and len(node.get_text(strip=True)) > 200:
            return " ".join(node.get_text(" ", strip=True).split())
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    return " ".join(p for p in paras if len(p) > 40)


def fetch_body(url: str, http=requests, delay: float = 1.0) -> str:
    try:
        if not allowed(url, http):
            return ""
        time.sleep(delay)  # 서버에 부담을 주지 않도록 간격 두기
        resp = http.get(url, headers={"User-Agent": UA}, timeout=15)
        resp.raise_for_status()
        return extract_text(resp.text)[:MAX_CHARS]
    except Exception:
        return ""


def longest_overlap(generated: str, source: str) -> int:
    """생성문과 원문이 연속으로 같은 가장 긴 글자 수."""
    if not generated or not source:
        return 0
    return SequenceMatcher(None, generated, source, autojunk=False).find_longest_match(0, len(generated), 0, len(source)).size
