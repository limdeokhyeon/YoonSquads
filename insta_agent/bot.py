"""뉴스 수집 → 텔레그램 검토 → 승인 시 예약 발행까지 잇는 오케스트레이터."""

from __future__ import annotations

import os
import re
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from .agent import run_due
from .article import fetch_body
from .cards import render_card
from .config import Config, update_env
from .content import NewsDraft, generate_news_draft
from .hosting import upload_image
from .images import generate_background
from .stock import fetch_unsplash, track_download
from .instagram import InstagramClient
from .news import collect, collect_breaking
from .queue import Queue
from .safety import redact
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


def make_cards(cfg: Config, cid: int, draft: NewsDraft, breaking: bool = False, reuse: bool = False) -> list[str]:
    """뉴스 카드 한 장을 만든다. 배경은 설정(PHOTO_SOURCE)에 따라 AI 이미지/Unsplash 사진/그라데이션.

    reuse=True면 검토 때 이미 받아 둔 배경을 다시 쓴다(승인 때 사진이 바뀌거나 비용이 또 나가지 않도록).
    사진을 못 구하면 기본 배경으로 계속한다.
    """
    out = os.path.join(CARD_DIR, str(cid))
    os.makedirs(out, exist_ok=True)
    bg, credit_file, dl_file = os.path.join(out, "bg.png"), os.path.join(out, "credit.txt"), os.path.join(out, "download.txt")
    if reuse and os.path.exists(bg):
        if os.path.exists(credit_file):
            draft.photo_credit = open(credit_file, encoding="utf-8").read().strip()
    else:
        for f in (bg, credit_file, dl_file):
            if os.path.exists(f):
                os.remove(f)
        try:
            if cfg.photo_source == "ai" and cfg.openai_key:
                generate_background(cfg, draft.image_prompt, bg)
            elif cfg.photo_source == "unsplash" and cfg.unsplash_key:
                draft.photo_credit, location = fetch_unsplash(cfg, draft.photo_query, bg)
                open(credit_file, "w", encoding="utf-8").write(draft.photo_credit)
                open(dl_file, "w", encoding="utf-8").write(location)
        except Exception as e:
            print(f"background error: {redact(e)}")
    has_bg = os.path.exists(bg)
    return [render_card(draft, out, cfg.font_path, bg if has_bg else None, cfg.ai_label and cfg.photo_source == "ai", breaking)]


def _send_review(cfg: Config, tg: Telegram, cid: int, item: dict, draft: NewsDraft, breaking: bool = False) -> None:
    paths = make_cards(cfg, cid, draft, breaking)
    tg.send_photo(paths[0], f"#{cid} 카드")
    tg.send(
        ("🚨 속보 후보\n" if breaking else "") + _preview_text(cid, item, draft),
        [("✅ 승인", f"ok:{cid}"), ("🔄 다시 쓰기", f"re:{cid}"), ("❌ 폐기", f"no:{cid}")],
    )


def propose(cfg: Config, queue: Queue, tg: Telegram) -> int:
    items = collect(cfg, queue.seen_links(), queue.recent_titles())
    sent = 0
    for item in items:
        try:
            data = item.to_dict()
            if cfg.fetch_body:
                data["body"] = fetch_body(item.link)
            draft = generate_news_draft(cfg, data, recent=queue.recent_styles())
            cid = queue.add_candidate(data, asdict(draft))
            _send_review(cfg, tg, cid, data, draft)
            sent += 1
        except Exception as e:
            tg.send(f"⚠️ 후보 생성 실패: {item.title[:40]}\n{redact(e)}")
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
            draft = generate_news_draft(cfg, data, recent=queue.recent_styles())
            draft.badge = "속보"  # 속보 감시로 들어온 기사는 항상 속보 배지
            cid = queue.add_candidate(data, asdict(draft), kind="breaking")
            _send_review(cfg, tg, cid, data, draft, breaking=True)
            sent += 1
        except Exception as e:
            print(f"breaking error: {redact(e)}")  # 5분마다 반복될 수 있어 텔레그램에는 보내지 않는다
            queue.add_candidate({**item.to_dict(), "skipped": redact(e)}, {}, kind="breaking_failed")
    return sent


def approve(cfg: Config, queue: Queue, tg: Telegram, cid: int) -> str:
    cand = queue.get_candidate(cid)
    if not cand or cand["status"] != "proposed":
        return "이미 처리된 후보입니다"
    draft = _draft(cand["draft"])
    paths = make_cards(cfg, cid, draft, cand.get("kind") == "breaking", reuse=True)
    urls = [upload_image(cfg, p) for p in paths]
    dl_file = os.path.join(CARD_DIR, str(cid), "download.txt")
    if os.path.exists(dl_file):  # Unsplash 사진을 실제로 쓰는 시점에 다운로드 집계
        track_download(cfg, open(dl_file, encoding="utf-8").read().strip())
        os.remove(dl_file)
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
    draft = generate_news_draft(cfg, cand["item"], feedback, recent=queue.recent_styles())
    queue.update_candidate(cid, draft=asdict(draft))
    _send_review(cfg, tg, cid, cand["item"], draft)


def _ack(tg: Telegram, callback_id: str, text: str = "") -> None:
    """버튼 응답. 너무 늦어 실패해도(query is too old) 본 작업은 계속하도록 오류를 삼킨다."""
    try:
        tg.answer_callback(callback_id, text)
    except Exception as e:
        print(f"callback ack error: {redact(e)}")


def handle_update(cfg: Config, queue: Queue, tg: Telegram, update: dict) -> None:
    if not tg.is_owner(update):  # 본인 외에는 무시
        return
    cb = update.get("callback_query")
    try:
        if cb:
            action, _, raw = cb["data"].partition(":")
            cid = int(raw)
            if action == "ok":
                _ack(tg, cb["id"], "승인 처리 중…")  # 업로드에 시간이 걸리므로 먼저 응답해 버튼이 오래 돌지 않게
                result = approve(cfg, queue, tg, cid)
                if result != "승인됨":
                    tg.send(result)
            elif action == "no":
                queue.update_candidate(cid, status="rejected")
                _ack(tg, cb["id"], "폐기했습니다")
            elif action == "re":
                _ack(tg, cb["id"], "다시 쓰는 중…")
                regenerate(cfg, queue, tg, cid)
            elif action == "rt":  # 여기서 cid 는 후보가 아니라 예약 글(post)의 번호
                _ack(tg, cb["id"], "다시 시도합니다" if queue.requeue(cid) else "이미 처리된 글입니다")
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
        tg.send(f"⚠️ 처리 중 오류: {redact(e)}")


TOKEN_REFRESH_DAYS = 30


def _notify(tg: Telegram, text: str) -> None:
    try:
        tg.send(text)
    except Exception as e:
        print(f"notify error: {redact(e)}")


def run_collect(cfg: Config, queue: Queue, tg: Telegram) -> int:
    """아침 정기 수집. 실패하면 조용히 넘기지 않고 텔레그램으로 알린다."""
    try:
        return propose(cfg, queue, tg)
    except Exception as e:
        _notify(tg, f"⚠️ 아침 뉴스 수집 실패: {redact(e)}\n/collect 로 다시 시도할 수 있어요")
        return 0


def run_breaking(cfg: Config, queue: Queue, tg: Telegram, state: dict, today=None) -> int:
    """속보 확인. 실패는 하루에 한 번만 알린다(정각마다 같은 오류로 알림이 쌓이지 않게)."""
    try:
        return propose_breaking(cfg, queue, tg)
    except Exception as e:
        today = today or datetime.now(KST).date()
        if state.get("notified_on") != today:
            state["notified_on"] = today
            _notify(tg, f"⚠️ 속보 확인 실패: {redact(e)}\n(같은 문제는 오늘 다시 알리지 않아요)")
        return 0


def report_results(tg: Telegram, results: list[tuple[int, str]]) -> None:
    """발행 결과를 알린다. 실패에는 '다시 시도' 버튼을 붙인다."""
    for pid, result in results:
        if result.startswith("expired"):
            _notify(tg, f"⏳ #{pid} 예약 시각에서 너무 오래 지나(서버가 꺼져 있었나요?) 발행하지 않았습니다. 낡은 뉴스가 올라가지 않게 한 조치예요.")
        elif result.startswith("failed"):
            detail = result[len("failed:"):]
            warn = "\n⚠️ 요청은 나갔는데 결과를 못 받았습니다. 인스타에 이미 올라갔을 수 있으니 계정을 먼저 확인하세요." if detail.startswith("[확인필요]") else ""
            try:
                tg.send(f"❌ #{pid} 발행 실패: {detail[:300]}{warn}", [("🔁 다시 시도", f"rt:{pid}")])
            except Exception as e:
                print(f"notify error: {redact(e)}")
        else:
            _notify(tg, f"📤 발행 결과 #{pid}: {result[:300]}")


def report_stuck(queue: Queue, tg: Telegram) -> int:
    """이전 실행에서 발행 도중 멈춘 글을 알린다. 중복 게시를 막기 위해 자동으로 다시 올리지는 않는다."""
    stuck = queue.stuck_publishing()
    for post in stuck:
        queue.mark_failed(post.id, "발행 도중 서버가 멈춤 — 인스타에 올라갔는지 확인 필요")
        _notify(tg, f"⚠️ #{post.id} 발행 도중 서버가 멈췄습니다. 인스타에 올라갔는지 확인해 주세요. 올라가지 않았다면 다시 승인해야 합니다.\n{post.caption[:80]}")
    return len(stuck)


def breaking_slot(cfg: Config, now: datetime):
    """속보를 확인할 시간대(한국시간 start~end시, 끝 시각 정각 포함)이면 현재 칸(날짜, 몇 번째 간격)을, 아니면 None.

    칸이 바뀔 때마다 한 번씩 확인하므로 간격이 60분이면 9:00, 10:00 … 18:00 정각에 확인한다."""
    minutes = now.hour * 60 + now.minute
    if not (cfg.breaking_start_hour * 60 <= minutes <= cfg.breaking_end_hour * 60):
        return None
    return (now.date(), minutes // max(cfg.breaking_poll_minutes, 1))



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
    last_slot = None
    breaking_state: dict = {}
    report_stuck(queue, tg)
    _notify(tg, "🤖 봇이 시작되었습니다. /collect 로 지금 수집할 수 있어요." + (f"\n🚨 속보 감시 켜짐: {cfg.breaking_start_hour:02d}:00~{cfg.breaking_end_hour:02d}:00 사이 {cfg.breaking_poll_minutes}분마다 확인, 하루 최대 {cfg.breaking_max_per_day}건" if cfg.breaking_enabled else ""))
    while True:
        try:
            now = datetime.now(KST)
            if now.hour >= cfg.collect_hour and last_collect != now.date():
                last_collect = now.date()
                run_collect(cfg, queue, tg)
            try:
                maybe_refresh_token(queue, ig, tg)
            except Exception as e:
                tg.send(f"⚠️ 인스타 토큰 갱신 실패: {redact(e)}\n만료 전에 Meta 대시보드에서 새 토큰을 발급하세요")
                queue.set_meta("ig_token_refreshed", datetime.now(timezone.utc).isoformat())  # 매 루프마다 재시도하지 않도록
            slot = breaking_slot(cfg, now) if cfg.breaking_enabled else None
            if slot is not None and slot != last_slot:
                last_slot = slot
                run_breaking(cfg, queue, tg, breaking_state)
            report_results(tg, run_due(queue, ig, max_late=timedelta(hours=cfg.post_max_late_hours)))
            for update in tg.get_updates(offset):
                offset = update["update_id"] + 1
                handle_update(cfg, queue, tg, update)
        except Exception as e:
            print(f"loop error: {redact(e)}")
            time.sleep(10)
