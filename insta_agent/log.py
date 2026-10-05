"""파일 로그(자동 순환): logs/app.log 를 1MB씩 3개까지만 남겨 디스크가 차지 않게 한다."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

log = logging.getLogger("insta")


def setup(log_dir: str = "logs") -> logging.Logger:
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    os.makedirs(log_dir, exist_ok=True)
    fh = RotatingFileHandler(os.path.join(log_dir, "app.log"), maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)
    sh = logging.StreamHandler()  # 화면(서비스는 serve.log)에는 경고 이상만
    sh.setLevel(logging.WARNING)
    sh.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    log.addHandler(sh)
    return log
