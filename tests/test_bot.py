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
        collect_hour=9, post_hours=[12, 18], imgbb_key="k", font_path="", card_footer="f", fetch_body=False, breaking_enabled=True, breaking_keywords=["속보"], breaking_poll_minutes=5, breaking_max_per_day=2, breaking_max_age_min=90,
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


def test_complete_falls_back_to_claude_cli(monkeypatch):
    from insta_agent import content

    calls = {}

    class P:
        returncode, stdout, stderr = 0, '{"headline":"h","bullets":["b"],"caption":"c","hashtags":[]}', ""

    def fake_run(cmd, **kw):
        calls["cmd"], calls["cwd"] = cmd, kw["cwd"]
        return P()

    monkeypatch.setattr(content.shutil, "which", lambda n: "/usr/bin/claude")
    monkeypatch.setattr(content.subprocess, "run", fake_run)
    d = content.generate_news_draft(make_cfg(anthropic_api_key=""), {"title": "t", "summary": "s", "link": "http://l"})
    assert d.headline == "h" and calls["cmd"][:2] == ["/usr/bin/claude", "-p"]
    assert "yoonsquads" not in calls["cwd"]  # 프로젝트 폴더가 아닌 임시 폴더


def test_complete_without_key_or_cli_errors(monkeypatch):
    from insta_agent import content

    monkeypatch.setattr(content.shutil, "which", lambda n: None)
    with pytest.raises(RuntimeError):
        content.complete(make_cfg(anthropic_api_key=""), "s", "u")


def test_get_updates_sends_long_poll_timeout():
    sent = {}

    class R:
        def json(self): return {"ok": True, "result": [{"update_id": 1}]}

    class H:
        def post(self, url, data, timeout):
            sent.update(url=url, data=data, timeout=timeout)
            return R()

    tg = Telegram("T", "1", http=H())
    assert tg.get_updates(offset=5, timeout=25) == [{"update_id": 1}]
    assert sent["data"]["timeout"] == 25 and sent["data"]["offset"] == 5
    assert sent["timeout"] == 35 and sent["url"].endswith("/getUpdates")


def test_extract_text_prefers_article_container():
    from insta_agent.article import extract_text

    html = "<html><body><div id='dic_area'>" + "본문 문장입니다. " * 30 + "</div><p>광고</p><script>x</script></body></html>"
    assert extract_text(html).startswith("본문 문장입니다.")


def test_fetch_body_respects_robots(monkeypatch):
    from insta_agent import article

    article._robots.clear()

    class R:
        def __init__(self, text, code=200): self.text, self.status_code = text, code
        def raise_for_status(self): pass

    class H:
        def get(self, url, headers=None, timeout=None):
            if url.endswith("robots.txt"):
                return R("User-agent: *\nDisallow: /")
            raise AssertionError("차단된 주소를 읽으면 안 됨")

    assert article.fetch_body("http://blocked.example/a", http=H(), delay=0) == ""


def test_overlap_triggers_rewrite(monkeypatch):
    from insta_agent import content

    body = "정부는 내년 예산안을 전년보다 크게 늘린 규모로 편성해 국회에 제출했다고 밝혔다 " * 2
    outputs = iter([
        '{"headline":"예산안","bullets":["b"],"caption":"정부는 내년 예산안을 전년보다 크게 늘린 규모로 편성해 국회에 제출했다고 밝혔다","hashtags":[]}',
        '{"headline":"예산안","bullets":["b"],"caption":"내년 나라 살림 계획이 국회로 넘어갔다","hashtags":[]}',
    ])
    monkeypatch.setattr(content, "complete", lambda cfg, s, u, max_tokens=1500: next(outputs))
    d = content.generate_news_draft(make_cfg(), {"title": "t", "summary": "s", "link": "l", "body": body})
    assert "나라 살림" in d.caption


def test_clear_rejects_only_proposed():
    q, tg = Queue(":memory:"), FakeTG()
    a = q.add_candidate({"link": "a"}, {})
    b = q.add_candidate({"link": "b"}, {})
    q.update_candidate(b, status="approved")
    class U(dict): pass
    upd = {"message": {"text": "/clear", "chat": {"id": 1}, "from": {"id": 1}}}
    bot.handle_update(make_cfg(), q, tg, upd)
    assert q.get_candidate(a)["status"] == "rejected" and q.get_candidate(b)["status"] == "approved"
    assert "1건" in tg.sent[-1]


def _hub_item(title, link, minutes_ago, now):
    from email.utils import format_datetime
    from insta_agent.news import NewsItem
    return NewsItem(title, "s", link, format_datetime(now - timedelta(minutes=minutes_ago)))


def test_breaking_filters_old_duplicate_and_unrelated(monkeypatch):
    from insta_agent import news

    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    items = [
        _hub_item("[속보] 정부, 내년 예산안 확정", "http://1", 5, now),
        _hub_item("속보 정부 내년 예산안 확정…국회 제출", "http://2", 6, now),   # 같은 사건
        _hub_item("[속보] 오래된 기사", "http://3", 300, now),                     # 너무 오래됨
        _hub_item("오늘의 날씨", "http://4", 3, now),                              # 속보 아님
        _hub_item("[속보] 환율 급등 1400원 돌파", "http://5", 10, now),
    ]
    monkeypatch.setattr(news, "search_news", lambda cfg, kw, limit=30, http=None: items)
    got = news.collect_breaking(make_cfg(), set(), [], limit=5, now=now)
    assert [i.link for i in got] == ["http://1", "http://5"]
    # 이미 보낸 사건은 제외
    got = news.collect_breaking(make_cfg(), set(), ["정부, 내년 예산안 확정"], limit=5, now=now)
    assert [i.link for i in got] == ["http://5"]


def test_breaking_daily_cap_and_instant_publish(monkeypatch):
    from insta_agent.news import NewsItem

    q, tg = Queue(":memory:"), FakeTG()
    tg.send_photo = lambda *a, **k: None
    now = datetime.now(timezone.utc)
    from email.utils import format_datetime
    mk = lambda t, n: NewsItem(t, "s", f"http://{n}", format_datetime(now))
    monkeypatch.setattr(bot, "collect_breaking", lambda cfg, seen, recent, limit: [mk("속보 가나다 사건", 1), mk("속보 완전히 다른 라마바 일", 2), mk("속보 셋째 아자차", 3)][:limit])
    monkeypatch.setattr(bot, "generate_news_draft", lambda cfg, item, fb="": NewsDraft("제목", ["가"], "본문", ["t"], item["link"]))
    monkeypatch.setattr(bot, "render_cards", lambda *a, **k: ["a.png", "b.png"])
    monkeypatch.setattr(bot, "upload_image", lambda cfg, p: "https://img/" + p)
    cfg = make_cfg()  # 하루 상한 2
    assert bot.propose_breaking(cfg, q, tg) == 2
    assert bot.propose_breaking(cfg, q, tg) == 0  # 상한 도달
    cid = q.get_candidate(1)
    assert cid["kind"] == "breaking"
    bot.approve(cfg, q, tg, 1)
    slot = q.list("pending")[0].scheduled_at
    assert slot - datetime.now(timezone.utc) < timedelta(minutes=3)  # 정해진 시각이 아니라 바로 발행
