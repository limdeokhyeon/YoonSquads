"""뉴스 수집 → 텔레그램 검토 → 승인 시 예약 발행까지 잇는 오케스트레이터."""

from __future__ import annotations

import os
import re
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from .agent import run_due
from .article import fetch_body
from .cards import render_cards
from .config import Config, update_env
from .content import NewsDraft, generate_news_draft
from .hosting import upload_image
from .instagram import InstagramClient
from .news import collect, collect_breaking
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


def _send_review(cfg: Config, tg: Telegram, cid: int, item: dict, draft: NewsDraft, breaking: bool = False) -> None:
    paths = render_cards(draft, os.path.join(CARD_DIR, str(cid)), cfg.font_path, cfg.card_footer)
    tg.send_photo(paths[0], f"#{cid} 표지")
    tg.send_photo(paths[1], f"#{cid} 본문")
    tg.send(
        ("🚨 속보 후보\n" if breaking else "") + _preview_text(cid, item, draft),
        [("✅ 승인", f"ok:{cid}"), ("🔄 다시 쓰기", f"re:{cid}"), ("❌ 폐기", f"no:{cid}")],
    )


def propose(cfg: Config, queue: Queue, tg: Telegram) -> int:
    items = collect(cfg, queue.seen_links())
    sent = 0
    for item in items:
        try:
            data = item.to_dict()
            if cfg.fetch_body:
                data["body"] = fetch_body(item.link)
            draft = generate_news_draft(cfg, data)
            cid = queue.add_candidate(data, asdict(draft))
            _send_review(cfg, tg, cid, data, draft)
            sent += 1
        except Exception as e:
            tg.send(f"⚠️ 후보 생성 실패: {item.title[:40]}\n{e}")
    if not sent:
        tg.send("새로 올릴 만한 뉴스를 찾지 못했습니다.")
    return sent


def propose_breaking(cfg: Config, queue: Queue, tg: Telegram) -> int:
    """속보 후보를 찾아 즉시 검토 요청을 보낸다. 하루 상한을 넘기면 조용히 건너뛴다."""
    room = cfg.breaking_max_per_day - queue.count_today("breaking")
    if room <= 0:
        return 0
    sent = 0
    for item in collect_breaking(cfg, queue.seen_links(), queue.recent_titles(), room):
        try:
            data = item.to_dict()
            if cfg.fetch_body:
                data["body"] = fetch_body(item.link)
            draft = generate_news_draft(cfg, data)
            cid = queue.add_candidate(data, asdict(draft), kind="breaking")
            _send_review(cfg, tg, cid, data, draft, breaking=True)
            sent += 1
        except Exception as e:
            print(f"breaking error: {e}")  # 5분마다 반복될 수 있어 텔레그램에는 보내지 않는다
            queue.add_candidate({**item.to_dict(), "skipped": str(e)}, {}, kind="breaking_failed")
    return sent


def approve(cfg: Config, queue: Queue, tg: Telegram, cid: int) -> str:
    cand = queue.get_candidate(cid)
    if not cand or cand["status"] != "proposed":
        return "이미 처리된 후보입니다"
    draft = _draft(cand["draft"])
    paths = render_cards(draft, os.path.join(CARD_DIR, str(cid)), cfg.font_path, cfg.card_footer)
    urls = [upload_image(cfg, p) for p in paths]
    if cand.get("kind") == "breaking":  # 속보는 시간이 생명이라 바로 발행
        slot = datetime.now(KST) + timedelta(minutes=2)
    else:
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
        elif text.startswith("/clear"):
            tg.send(f"🧹 검토 대기 중이던 후보 {queue.reject_all_proposed()}건을 모두 폐기했습니다")
        elif text.startswith(("/start", "/help")):
            tg.send("명령어\n/collect — 지금 뉴스 수집\n/clear — 검토 대기 후보 모두 폐기\n수정 <번호> <요청> — 예) 수정 3 더 짧게\n버튼으로 승인/다시쓰기/폐기")
    except Exception as e:
        tg.send(f"⚠️ 처리 중 오류: {e}")


TOKEN_REFRESH_DAYS = 30


def maybe_refresh_token(queue: Queue, ig: InstagramClient, tg: Telegram, now: datetime | None = None) -> bool:
    """Instagram 로그인 토큰(60일 만료)을 30일마다 연장하고 .env에 저장한다."""
    if ig.host != "graph.instagram.com":
        return False
    now = now or datetime.now(timezone.utc)
    last = queue.get_meta("ig_token_refreshed")
    if last is None:  # 처음엔 방금 발급한 토큰이라고 보고 기준 시각만 기록
        queue.set_meta("ig_token_refreshed", now.isoformat())
        return False
    if now - datetime.fromisoformat(last) < timedelta(days=TOKEN_REFRESH_DAYS):
        return False
    token, expires = ig.refresh_token()
    update_env("IG_ACCESS_TOKEN", token)
    queue.set_meta("ig_token_refreshed", now.isoformat())
    tg.send(f"🔑 인스타 토큰을 갱신했습니다 (유효 {expires // 86400}일)")
    return True


def serve(cfg: Config) -> None:
    """상시 실행: 텔레그램 응답 처리 + 매일 수집 + 예약 발행."""
    queue, tg, ig = Queue(cfg.db_path), Telegram(cfg.telegram_token, cfg.telegram_chat_id), InstagramClient(cfg)
    offset = None
    # 켤 때마다 후보가 쏟아지지 않도록, 이미 수집 시각이 지났으면 오늘 몫은 건너뛴다
    now0 = datetime.now(KST)
    last_collect = now0.date() if now0.hour >= cfg.collect_hour else None
    next_breaking = 0.0
    tg.send("🤖 봇이 시작되었습니다. /collect 로 지금 수집할 수 있어요." + (f"\n🚨 속보 감시 켜짐: {cfg.breaking_poll_minutes}분마다 확인, 하루 최대 {cfg.breaking_max_per_day}건" if cfg.breaking_enabled else ""))
    while True:
        try:
            now = datetime.now(KST)
            if now.hour >= cfg.collect_hour and last_collect != now.date():
                last_collect = now.date()
                propose(cfg, queue, tg)
            try:
                maybe_refresh_token(queue, ig, tg)
            except Exception as e:
                tg.send(f"⚠️ 인스타 토큰 갱신 실패: {e}\n만료 전에 Meta 대시보드에서 새 토큰을 발급하세요")
                queue.set_meta("ig_token_refreshed", datetime.now(timezone.utc).isoformat())  # 매 루프마다 재시도하지 않도록
            if cfg.breaking_enabled and time.monotonic() >= next_breaking:
                next_breaking = time.monotonic() + cfg.breaking_poll_minutes * 60
                propose_breaking(cfg, queue, tg)
            for result in run_due(queue, ig):
                tg.send(f"📤 발행 결과 #{result[0]}: {result[1][:300]}")
            for update in tg.get_updates(offset):
                offset = update["update_id"] + 1
                handle_update(cfg, queue, tg, update)
        except Exception as e:
            print(f"loop error: {e}")
            time.sleep(10)
