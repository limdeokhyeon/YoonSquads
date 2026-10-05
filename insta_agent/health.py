"""서버 생존 신고(heartbeat): 일정 간격으로 모니터링 주소(healthchecks.io 등)에 신호를 보낸다.

맥북이 꺼지거나 서버가 멈추면 신호가 끊기고, 모니터링 서비스가 이메일로 알려 준다.
HEALTHCHECK_URL 이 없으면 아무것도 하지 않는다.
"""

from __future__ import annotations

import time

import requests

from .log import log
from .safety import redact


class Heartbeat:
    def __init__(self, url: str, interval: float = 300.0, http=requests, clock=time.monotonic):
        self.url, self.interval, self.http, self.clock = url.strip(), interval, http, clock
        self.last: float | None = None

    def beat(self) -> bool:
        """간격이 지났으면 신호를 보낸다. 모니터링 서비스가 잠깐 안 돼도 서버 동작에는 영향이 없다."""
        if not self.url:
            return False
        now = self.clock()
        if self.last is not None and now - self.last < self.interval:
            return False
        self.last = now
        try:
            self.http.get(self.url, timeout=10)
            return True
        except Exception as e:
            log.warning(f"heartbeat error: {redact(e)}")
            return False

    def fail(self, message: str = "") -> None:
        """서버가 계속 오류를 내고 있을 때 실패 신호를 보낸다(healthchecks.io 의 /fail)."""
        if not self.url:
            return
        try:
            self.http.post(self.url.rstrip("/") + "/fail", data=redact(message)[:500], timeout=10)
        except Exception as e:
            log.warning(f"heartbeat error: {redact(e)}")
