"""로그·텔레그램 오류 메시지에 토큰이 새지 않도록 가린다.

requests 의 연결 오류 메시지에는 요청 주소가 통째로 들어가는데, 텔레그램 주소에는 봇 토큰이 들어 있다.
화면 캡처나 로그를 공유할 때 토큰이 같이 노출되는 일을 막는다.
"""

from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"bot\d{6,}:[A-Za-z0-9_-]{20,}"), "bot***"),
    (re.compile(r"(access_token=)[^&\s'\"]+"), r"\1***"),
    (re.compile(r"\b(?:IGA|EAA)[A-Za-z0-9_-]{30,}"), "***"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), "sk-***"),
    (re.compile(r"(Client-ID\s+)[A-Za-z0-9_-]{20,}"), r"\1***"),
]


def redact(text) -> str:
    out = str(text)
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    return out
