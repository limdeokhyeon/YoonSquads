"""예약된 게시물을 발행하는 실행기."""

from __future__ import annotations

from .instagram import InstagramClient
from .queue import Queue


def run_due(queue: Queue, client: InstagramClient, dry_run: bool = False) -> list[tuple[int, str]]:
    """발행 시각이 지난 게시물을 모두 처리한다. (id, 결과) 목록 반환."""
    results = []
    for post in queue.due():
        if dry_run:
            results.append((post.id, "dry-run"))
            continue
        try:
            media_id = client.publish(post.image_urls, post.caption)
            queue.mark_published(post.id, media_id)
            results.append((post.id, f"published:{media_id}"))
        except Exception as e:  # 한 건 실패가 나머지를 막지 않도록
            queue.mark_failed(post.id, str(e))
            results.append((post.id, f"failed:{e}"))
    return results
