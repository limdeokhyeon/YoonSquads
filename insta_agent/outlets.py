"""기사 원문 주소에서 언론사 이름을 알아낸다. 모르는 도메인은 도메인 그대로 보여 준다."""

from __future__ import annotations

from urllib.parse import urlparse

OUTLETS = {
    "yna.co.kr": "연합뉴스", "news1.kr": "뉴스1", "newsis.com": "뉴시스", "kbs.co.kr": "KBS", "mbn.co.kr": "MBN",
    "sbs.co.kr": "SBS", "imbc.com": "MBC", "ytn.co.kr": "YTN", "jtbc.co.kr": "JTBC", "tvchosun.com": "TV조선",
    "chosun.com": "조선일보", "joongang.co.kr": "중앙일보", "donga.com": "동아일보", "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문", "hankookilbo.com": "한국일보", "mk.co.kr": "매일경제", "hankyung.com": "한국경제",
    "sedaily.com": "서울경제", "heraldcorp.com": "헤럴드경제", "etnews.com": "전자신문", "edaily.co.kr": "이데일리",
    "mt.co.kr": "머니투데이", "fnnews.com": "파이낸셜뉴스", "nocutnews.co.kr": "노컷뉴스", "ohmynews.com": "오마이뉴스",
    "pressian.com": "프레시안", "seoul.co.kr": "서울신문", "segye.com": "세계일보", "munhwa.com": "문화일보",
    "kmib.co.kr": "국민일보", "naeil.com": "내일신문", "dt.co.kr": "디지털타임스", "asiae.co.kr": "아시아경제",
    "newspim.com": "뉴스핌", "kukinews.com": "쿠키뉴스", "mydaily.co.kr": "마이데일리", "imaeil.com": "매일신문",
    "busan.com": "부산일보", "kookje.co.kr": "국제신문", "ebn.co.kr": "EBN", "inews24.com": "아이뉴스24",
    "zdnet.co.kr": "지디넷코리아", "bloter.net": "블로터", "ajunews.com": "아주경제", "news.naver.com": "네이버 뉴스",
    "n.news.naver.com": "네이버 뉴스",
}


def outlet_name(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    parts = host.split(".")
    for i in range(len(parts) - 1):  # news.example.co.kr → example.co.kr 순으로 줄여 가며 찾는다
        name = OUTLETS.get(".".join(parts[i:]))
        if name:
            return name
    return host
