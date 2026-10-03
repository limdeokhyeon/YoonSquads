"""SQLite 기반 예약 발행 큐."""

from __future__ import annotations

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


CANDIDATES = """
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link TEXT NOT NULL UNIQUE,
    item TEXT NOT NULL,
    draft TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',   -- proposed | approved | rejected
    post_id INTEGER
)"""


class Queue:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute(SCHEMA)
        self.db.execute(CANDIDATES)

    # --- 뉴스 후보(텔레그램 검토 대기) ---
    def seen_links(self) -> set[str]:
        return {r["link"] for r in self.db.execute("SELECT link FROM candidates")}

    def add_candidate(self, item: dict, draft: dict) -> int:
        cur = self.db.execute(
            "INSERT INTO candidates (link, item, draft) VALUES (?,?,?)",
            (item["link"], json.dumps(item, ensure_ascii=False), json.dumps(draft, ensure_ascii=False)),
        )
        self.db.commit()
        return cur.lastrowid

    def get_candidate(self, cid: int) -> dict | None:
        r = self.db.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()
        if not r:
            return None
        return {"id": r["id"], "item": json.loads(r["item"]), "draft": json.loads(r["draft"]), "status": r["status"]}

    def update_candidate(self, cid: int, *, draft: dict | None = None, status: str | None = None, post_id: int | None = None) -> None:
        if draft is not None:
            self.db.execute("UPDATE candidates SET draft=? WHERE id=?", (json.dumps(draft, ensure_ascii=False), cid))
        if status is not None:
            self.db.execute("UPDATE candidates SET status=? WHERE id=?", (status, cid))
        if post_id is not None:
            self.db.execute("UPDATE candidates SET post_id=? WHERE id=?", (post_id, cid))
        self.db.commit()

    def reject_all_proposed(self) -> int:
        cur = self.db.execute("UPDATE candidates SET status='rejected' WHERE status='proposed'")
        self.db.commit()
        return cur.rowcount

    def pending_slots(self) -> list[datetime]:
        return [p.scheduled_at for p in self.list("pending")]

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
