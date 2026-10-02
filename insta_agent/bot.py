"""뉴스 수집 → 텔레그램 검토 → 승인 시 예약 발행까지 잇는 오케스트레이터."""

from __future__ import annotations

import os
import re
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from .agent import run_due
from .cards import render_cards
from .config import Config
from .content import NewsDraft, generate_news_draft
from .hosting import upload_image
from .instagram import InstagramClient
from .news import collect
from .queue import Queue
from .telegram import Telegram

KST = timezone(timedelta(hours=9))
CARD_DIR = "cards"


def next_slot(post_hours: list[int], taken: list[datetime], now: datetime | None = None) -> datetime:
    """오늘부터 차례로 훑어, 아직 비어 있는 다음 게시 시각(KST)을 반환."""
    now = (now or datetime.now(KST)).astimezone(KST)
    taken_set = {t.astimezone(KST).replace(minute=0, second=0, microsecond=0) for t in taken}
    for day in range(0, 30):
        for h in sorted(post_hours):
            slot = (now + timedelta(days=day)).replace(hour=h, minute=0, second=0, microsecond=0)
            if slot > now + timedelta(minutes=5) and slot not in taken_set:
                return slot
    raise RuntimeError("30일 안에 빈 게시 시각이 없습니다")


def _draft(d: dict) -> NewsDraft:
    return NewsDraft(**d)


def _preview_text(cid: int, item: dict, draft: NewsDraft) -> str:
    bullets = "\n".join(f"  {i}. {b}" for i, b in enumerate(draft.bullets, 1))
    return (
        f"[#{cid}] {draft.headline}\n\n{bullets}\n\n{draft.caption}\n\n"
        f"#{' #'.join(draft.hashtags)}\n\n원문: {item['link']}"
    )


def _send_review(cfg: Config, tg: Telegram, cid: int, item: dict, draft: NewsDraft) -> None:
    paths = render_cards(draft, os.path.join(CARD_DIR, str(cid)), cfg.font_path)
    tg.send_photo(paths[0], f"#{cid} 표지")
    tg.send_photo(paths[1], f"#{cid} 본문")
    tg.send(
        _preview_text(cid, item, draft),
        [("✅ 승인", f"ok:{cid}"), ("🔄 다시 쓰기", f"re:{cid}"), ("❌ 폐기", f"no:{cid}")],
    )


def propose(cfg: Config, queue: Queue, tg: Telegram) -> int:
    items = collect(cfg, queue.seen_links())
    sent = 0
    for item in items:
        try:
            draft = generate_news_draft(cfg, item.to_dict())
            cid = queue.add_candidate(item.to_dict(), asdict(draft))
            _send_review(cfg, tg, cid, item.to_dict(), draft)
            sent += 1
        except Exception as e:
            tg.send(f"⚠️ 후보 생성 실패: {item.title[:40]}\n{e}")
    if not sent:
        tg.send("새로 올릴 만한 뉴스를 찾지 못했습니다.")
    return sent


def approve(cfg: Config, queue: Queue, tg: Telegram, cid: int) -> str:
    cand = queue.get_candidate(cid)
    if not cand or cand["status"] != "proposed":
        return "이미 처리된 후보입니다"
    draft = _draft(cand["draft"])
    paths = render_cards(draft, os.path.join(CARD_DIR, str(cid)), cfg.font_path)
    urls = [upload_image(cfg, p) for p in paths]
    slot = next_slot(cfg.post_hours, queue.pending_slots())
    post_id = queue.add(draft.full_text(), urls, slot)
    queue.update_candidate(cid, status="approved", post_id=post_id)
    when = slot.astimezone(KST).strftime("%m/%d %H:%M")
    tg.send(f"✅ #{cid} 승인 — {when}(KST)에 발행 예약했습니다")
    return "승인됨"


def regenerate(cfg: Config, queue: Queue, tg: Telegram, cid: int, feedback: str = "") -> None:
    cand = queue.get_candidate(cid)
    if not cand or cand["status"] != "proposed":
        tg.send("이미 처리된 후보입니다")
        return
    draft = generate_news_draft(cfg, cand["item"], feedback)
    queue.update_candidate(cid, draft=asdict(draft))
    _send_review(cfg, tg, cid, cand["item"], draft)


def handle_update(cfg: Config, queue: Queue, tg: Telegram, update: dict) -> None:
    if not tg.is_owner(update):  # 본인 외에는 무시
        return
    cb = update.get("callback_query")
    try:
        if cb:
            action, _, raw = cb["data"].partition(":")
            cid = int(raw)
            if action == "ok":
                tg.answer_callback(cb["id"], approve(cfg, queue, tg, cid))
            elif action == "no":
                queue.update_candidate(cid, status="rejected")
                tg.answer_callback(cb["id"], "폐기했습니다")
            elif action == "re":
                tg.answer_callback(cb["id"], "다시 쓰는 중…")
                regenerate(cfg, queue, tg, cid)
            return
        text = (update.get("message") or {}).get("text", "")
        m = re.match(r"^수정\s+#?(\d+)\s+(.+)", text, re.S)
        if m:
            regenerate(cfg, queue, tg, int(m.group(1)), m.group(2).strip())
        elif text.startswith("/collect"):
            propose(cfg, queue, tg)
        elif text.startswith(("/start", "/help")):
            tg.send("명령어\n/collect — 지금 뉴스 수집\n수정 <번호> <요청> — 예) 수정 3 더 짧게\n버튼으로 승인/다시쓰기/폐기")
    except Exception as e:
        tg.send(f"⚠️ 처리 중 오류: {e}")


def serve(cfg: Config) -> None:
    """상시 실행: 텔레그램 응답 처리 + 매일 수집 + 예약 발행."""
    queue, tg, ig = Queue(cfg.db_path), Telegram(cfg.telegram_token, cfg.telegram_chat_id), InstagramClient(cfg)
    offset, last_collect = None, None
    tg.send("🤖 봇이 시작되었습니다. /collect 로 지금 수집할 수 있어요.")
    while True:
        try:
            now = datetime.now(KST)
            if now.hour >= cfg.collect_hour and last_collect != now.date():
                last_collect = now.date()
                propose(cfg, queue, tg)
            for result in run_due(queue, ig):
                tg.send(f"📤 발행 결과 #{result[0]}: {result[1][:300]}")
            for update in tg.get_updates(offset):
                offset = update["update_id"] + 1
                handle_update(cfg, queue, tg, update)
        except Exception as e:
            print(f"loop error: {e}")
            time.sleep(10)
