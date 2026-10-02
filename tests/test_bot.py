from datetime import datetime, timedelta, timezone

import pytest

from insta_agent import bot
from insta_agent.cards import render_cards
from insta_agent.config import Config
from insta_agent.content import NewsDraft, parse_news_draft
from insta_agent.news import clean, collect
from insta_agent.queue import Queue
from insta_agent.telegram import Telegram

KST = timezone(timedelta(hours=9))


def make_cfg(**kw):
    base = dict(
        anthropic_api_key="", ig_user_id="", ig_access_token="", graph_version="v21.0", model="m",
        brand_voice="", db_path=":memory:", naver_client_id="", naver_client_secret="",
        telegram_token="T", telegram_chat_id="1", news_keywords=["a", "b"], daily_count=3,
        collect_hour=9, post_hours=[12, 18], imgbb_key="k", font_path="",
    )
    base.update(kw)
    return Config(**base)


def test_clean_strips_tags_and_entities():
    assert clean("<b>임신</b> &quot;팁&quot;") == '임신 "팁"'


def test_next_slot_skips_taken_and_past():
    now = datetime(2026, 10, 2, 13, 0, tzinfo=KST)
    taken = [datetime(2026, 10, 2, 18, 0, tzinfo=KST)]
    assert bot.next_slot([12, 18], taken, now) == datetime(2026, 10, 3, 12, 0, tzinfo=KST)


def test_collect_alternates_keywords_and_dedupes(monkeypatch):
    from insta_agent import news

    def fake(cfg, kw, limit=30, http=None):
        items = [news.NewsItem(f"{kw}{i}", "s", f"http://{kw}{i}", "d") for i in range(3)]
        return items + [news.NewsItem("무관한 기사", "무관", "http://other", "d")]

    monkeypatch.setattr(news, "search_news", fake)
    got = collect(make_cfg(), seen={"http://a0"})
    assert [i.title for i in got] == ["a1", "b0", "a2"]


def test_parse_news_draft():
    d = parse_news_draft('{"headline":"제목","bullets":["가","나"],"caption":"본문","hashtags":["#x"]}', "http://l")
    assert d.hashtags == ["x"] and "출처: http://l" in d.full_text()
    with pytest.raises(ValueError):
        parse_news_draft('{"headline":"t","bullets":[],"caption":"c"}', "l")


class FakeTG(Telegram):
    def __init__(self, owner="1"):
        super().__init__("T", owner)
        self.sent = []

    def send(self, text, buttons=None):
        self.sent.append(text)

    def answer_callback(self, callback_id, text=""):
        self.sent.append(f"cb:{text}")


def _update(chat, user, data):
    return {"callback_query": {"id": "x", "data": data, "from": {"id": user}, "message": {"chat": {"id": chat}}}}


def test_non_owner_ignored():
    tg, q = FakeTG(), Queue(":memory:")
    bot.handle_update(make_cfg(), q, tg, _update(1, 999, "no:1"))
    assert tg.sent == []


def test_reject_and_approve_flow(monkeypatch):
    q, tg = Queue(":memory:"), FakeTG()
    draft = NewsDraft("제목", ["가"], "본문", ["t"], "http://l").__dict__
    cid = q.add_candidate({"title": "t", "summary": "s", "link": "http://l", "pub_date": ""}, draft)
    monkeypatch.setattr(bot, "render_cards", lambda *a, **k: ["a.png", "b.png"])
    monkeypatch.setattr(bot, "upload_image", lambda cfg, p: f"https://img/{p}")
    bot.handle_update(make_cfg(), q, tg, _update(1, 1, f"ok:{cid}"))
    post = q.list("pending")[0]
    assert post.image_urls == ["https://img/a.png", "https://img/b.png"]
    assert q.get_candidate(cid)["status"] == "approved"
    bot.handle_update(make_cfg(), q, tg, _update(1, 1, f"ok:{cid}"))  # 중복 승인 방지
    assert len(q.list("pending")) == 1


def test_render_cards(tmp_path):
    from insta_agent.cards import FONT_CANDIDATES
    import os

    font = next((p for p in FONT_CANDIDATES + ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"] if os.path.exists(p)), None)
    if not font:
        pytest.skip("한글 폰트 없음")
    paths = render_cards(NewsDraft("임신 초기 영양제 가이드", ["엽산 챙기기", "카페인 줄이기"], "c", [], "l"), str(tmp_path), font)
    assert all(os.path.getsize(p) > 1000 for p in paths)


def test_search_news_uses_api_hub():
    from insta_agent import news

    seen = {}

    class R:
        def raise_for_status(self): pass
        def json(self): return {"items": [{"title": "<b>A</b>", "description": "d", "link": "http://x", "pubDate": "p"}]}

    class H:
        def get(self, url, headers, params, timeout):
            seen.update(url=url, headers=headers, params=params)
            return R()

    got = news.search_news(make_cfg(naver_client_id="id", naver_client_secret="sec"), "임신", http=H())
    assert seen["url"] == "https://naverapihub.apigw.ntruss.com/search/v1/news"
    assert seen["headers"] == {"X-NCP-APIGW-API-KEY-ID": "id", "X-NCP-APIGW-API-KEY": "sec"}
    assert got[0].title == "A"
