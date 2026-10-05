"""예약된 게시물을 발행하는 실행기."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .instagram import InstagramClient
from .queue import Queue
from .safety import redact


def run_due(
    queue: Queue,
    client: InstagramClient,
    dry_run: bool = False,
    max_late: timedelta | None = None,
    now: datetime | None = None,
) -> list[tuple[int, str]]:
    """발행 시각이 지난 게시물을 모두 처리한다. (id, 결과) 목록 반환.

    max_late보다 오래 지난 글은 발행하지 않고 expired 로 둔다(서버가 오래 꺼져 있다 켜졌을 때 낡은 뉴스가 올라가지 않게).
    """
    now = now or datetime.now(timezone.utc)
    results = []
    for post in queue.due(now):
        if dry_run:
            results.append((post.id, "dry-run"))
            continue
        late = now - post.scheduled_at
        if max_late is not None and late > max_late:
            queue.mark_expired(post.id, f"예약 시각에서 {late.total_seconds() / 3600:.1f}시간 지나 발행하지 않음")
            results.append((post.id, f"expired:{late.total_seconds() / 3600:.1f}시간 지남"))
            continue
        queue.mark_publishing(post.id)  # 발행 도중 꺼져도 다시 자동 발행되지 않도록
        try:
            media_id = client.publish(post.image_urls, post.caption)
            queue.mark_published(post.id, media_id)
            results.append((post.id, f"published:{media_id}"))
        except Exception as e:  # 한 건 실패가 나머지를 막지 않도록
            msg = ("[확인필요] " if getattr(e, "ambiguous", False) else "") + redact(e)
            queue.mark_failed(post.id, msg)
            results.append((post.id, f"failed:{msg}"))
    return results
