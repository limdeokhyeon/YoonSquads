"""SQLite 기반 예약 발행 큐."""
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caption TEXT NOT NULL,
    image_urls TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | published | failed
    media_id TEXT,
    error TEXT
)"""


@dataclass
class Post:
    id: int
    caption: str
    image_urls: list[str]
    scheduled_at: datetime
    status: str
    media_id: str | None
    error: str | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row(r: sqlite3.Row) -> Post:
    return Post(
        r["id"], r["caption"], json.loads(r["image_urls"]),
        datetime.fromisoformat(r["scheduled_at"]), r["status"], r["media_id"], r["error"],
    )


class Queue:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute(SCHEMA)

    def add(self, caption: str, image_urls: list[str], when: datetime) -> int:
        if when.tzinfo is None:
            raise ValueError("예약 시각에는 시간대 정보가 필요합니다")
        cur = self.db.execute(
            "INSERT INTO posts (caption, image_urls, scheduled_at) VALUES (?,?,?)",
            (caption, json.dumps(image_urls), when.astimezone(timezone.utc).isoformat()),
        )
        self.db.commit()
        return cur.lastrowid

    def due(self, now: datetime | None = None) -> list[Post]:
        rows = self.db.execute(
            "SELECT * FROM posts WHERE status='pending' AND scheduled_at <= ? ORDER BY scheduled_at",
            ((now or _now()).isoformat(),),
        ).fetchall()
        return [_row(r) for r in rows]

    def list(self, status: str | None = None) -> list[Post]:
        q, args = "SELECT * FROM posts", ()
        if status:
            q, args = q + " WHERE status=?", (status,)
        return [_row(r) for r in self.db.execute(q + " ORDER BY scheduled_at", args)]

    def mark_published(self, post_id: int, media_id: str) -> None:
        self.db.execute("UPDATE posts SET status='published', media_id=? WHERE id=?", (media_id, post_id))
        self.db.commit()

    def mark_failed(self, post_id: int, error: str) -> None:
        self.db.execute("UPDATE posts SET status='failed', error=? WHERE id=?", (error, post_id))
        self.db.commit()
