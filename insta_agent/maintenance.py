"""오래된 카드 이미지·배경 파일을 정리한다(2015년형 맥북처럼 디스크가 넉넉하지 않아도 오래 돌도록)."""

from __future__ import annotations

import os
import shutil
import time

from .queue import Queue


def _size(path: str) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def cleanup_cards(cards_dir: str, queue: Queue, keep_days: int = 14, now: float | None = None) -> tuple[int, int]:
    """keep_days 보다 오래된 카드 폴더를 지운다. 아직 검토 대기 중인 후보는 3배 기간까지 남긴다.

    (지운 폴더 수, 확보한 바이트)를 돌려준다."""
    if not os.path.isdir(cards_dir):
        return 0, 0
    now = now or time.time()
    removed = freed = 0
    for name in os.listdir(cards_dir):
        path = os.path.join(cards_dir, name)
        if not (os.path.isdir(path) and name.isdigit()):
            continue
        age_days = (now - os.path.getmtime(path)) / 86400
        if age_days < keep_days:
            continue
        cand = queue.get_candidate(int(name))
        if cand and cand["status"] == "proposed" and age_days < keep_days * 3:
            continue
        freed += _size(path)
        shutil.rmtree(path, ignore_errors=True)
        removed += 1
    return removed, freed
