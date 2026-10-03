from datetime import datetime, timedelta, timezone

import pytest

from insta_agent import bot
from insta_agent.cards import render_card
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
        collect_hour=9, post_hours=[12, 18], imgbb_key="k", font_path="", ai_label=True, brand_hashtag="", photo_source="none", unsplash_key="", openai_key="", openai_image_model="m", fetch_body=False, breaking_enabled=True, breaking_keywords=["속보"], breaking_poll_minutes=5, breaking_max_per_day=2, breaking_max_age_min=90,
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
    assert d.hashtags == ["x"] and "출처: 기사 원문 http://l" in d.full_text()
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
    monkeypatch.setattr(bot, "render_card", lambda *a, **k: "a.png")
    monkeypatch.setattr(bot.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr(bot, "upload_image", lambda cfg, p: f"https://img/{p}")
    bot.handle_update(make_cfg(), q, tg, _update(1, 1, f"ok:{cid}"))
    post = q.list("pending")[0]
    assert post.image_urls == ["https://img/a.png"]  # 카드는 한 장
    assert q.get_candidate(cid)["status"] == "approved"
    bot.handle_update(make_cfg(), q, tg, _update(1, 1, f"ok:{cid}"))  # 중복 승인 방지
    assert len(q.list("pending")) == 1


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
    monkeypatch.setattr(bot, "generate_news_draft", lambda cfg, item, fb="", **k: NewsDraft("제목", ["가"], "본문", ["t"], item["link"]))
    monkeypatch.setattr(bot, "render_card", lambda *a, **k: "a.png")
    monkeypatch.setattr(bot.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr(bot, "upload_image", lambda cfg, p: "https://img/" + p)
    cfg = make_cfg()  # 하루 상한 2
    assert bot.propose_breaking(cfg, q, tg) == 2
    assert bot.propose_breaking(cfg, q, tg) == 0  # 상한 도달
    cid = q.get_candidate(1)
    assert cid["kind"] == "breaking"
    bot.approve(cfg, q, tg, 1)
    slot = q.list("pending")[0].scheduled_at
    assert slot - datetime.now(timezone.utc) < timedelta(minutes=3)  # 정해진 시각이 아니라 바로 발행


def test_instagram_host_and_me_for_igaa_token():
    from insta_agent.instagram import InstagramClient, api_host

    assert api_host("IGAAabc") == "graph.instagram.com" and api_host("EAAabc") == "graph.facebook.com"
    c = InstagramClient(make_cfg(ig_user_id="", ig_access_token="IGAAx"))
    assert c.base.startswith("https://graph.instagram.com/") and c.user == "me"
    c2 = InstagramClient(make_cfg(ig_user_id="123", ig_access_token="EAAx"))
    assert c2.base.startswith("https://graph.facebook.com/") and c2.user == "123"


def test_refresh_token_and_env_update(tmp_path):
    from insta_agent.config import update_env
    from insta_agent.instagram import InstagramClient

    class R:
        status_code = 200
        text = ""
        def json(self): return {"access_token": "IGAAnew", "token_type": "bearer", "expires_in": 5184000}

    class S:
        def get(self, url, params, timeout):
            assert url == "https://graph.instagram.com/refresh_access_token"
            assert params["grant_type"] == "ig_refresh_token" and params["access_token"] == "IGAAold"
            return R()

    c = InstagramClient(make_cfg(ig_access_token="IGAAold"), session=S())
    assert c.refresh_token() == ("IGAAnew", 5184000) and c.token == "IGAAnew"
    env = tmp_path / ".env"
    env.write_text("A=1\nIG_ACCESS_TOKEN=IGAAold\n")
    update_env("IG_ACCESS_TOKEN", "IGAAnew", str(env))
    update_env("NEW", "x", str(env))
    assert env.read_text() == "A=1\nIG_ACCESS_TOKEN=IGAAnew\nNEW=x\n"


def test_maybe_refresh_token_schedule(monkeypatch, tmp_path):
    from insta_agent.instagram import InstagramClient

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("IG_ACCESS_TOKEN=IGAAold\n")
    q, tg = Queue(":memory:"), FakeTG()
    ig = InstagramClient(make_cfg(ig_access_token="IGAAold"))
    monkeypatch.setattr(ig, "refresh_token", lambda: ("IGAAnew", 5184000))
    t0 = datetime(2026, 10, 3, tzinfo=timezone.utc)
    assert bot.maybe_refresh_token(q, ig, tg, now=t0) is False                      # 첫 실행: 기준 시각만 기록
    assert bot.maybe_refresh_token(q, ig, tg, now=t0 + timedelta(days=10)) is False  # 아직 이름
    assert bot.maybe_refresh_token(q, ig, tg, now=t0 + timedelta(days=31)) is True
    assert "IGAAnew" in (tmp_path / ".env").read_text()


def test_publishing_limit_parses_quota():
    from insta_agent.instagram import InstagramClient

    class R:
        status_code = 200
        text = ""
        def json(self): return {"data": [{"quota_usage": 2, "config": {"quota_total": 50, "quota_duration": 86400}}]}

    class S:
        def request(self, method, url, params, timeout):
            assert url == "https://graph.instagram.com/v21.0/me/content_publishing_limit"
            assert params["fields"] == "quota_usage,config"
            return R()

    c = InstagramClient(make_cfg(ig_user_id="", ig_access_token="IGAAx"), session=S())
    assert c.publishing_limit() == {"quota_usage": 2, "quota_total": 50}


def test_ai_background_falls_back_when_generation_fails(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    got = {}
    monkeypatch.setattr(bot, "generate_background", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("quota")))
    monkeypatch.setattr(bot, "render_card", lambda draft, out, font, bg, label, breaking: got.setdefault("bg", bg) or "x.png")
    cfg = make_cfg(photo_source="ai", openai_key="k")
    bot.make_cards(cfg, 1, NewsDraft("h", ["b"], "c", [], "l"))
    assert got["bg"] is None  # 실패해도 기본 배경으로 계속


def test_generate_background_decodes_b64(tmp_path):
    import base64
    from insta_agent.images import generate_background

    class R:
        def raise_for_status(self): pass
        def json(self): return {"data": [{"b64_json": base64.b64encode(b"PNGDATA").decode()}]}

    class H:
        def post(self, url, headers, json, timeout):
            assert url.endswith("/images/generations") and headers["Authorization"] == "Bearer k"
            assert "No text" in json["prompt"] and json["size"] == "1024x1536"
            return R()

    out = generate_background(make_cfg(openai_key="k"), "a blue shape", str(tmp_path / "bg.png"), http=H())
    assert open(out, "rb").read() == b"PNGDATA"


def _font():
    import os
    from insta_agent.cards import FONT_CANDIDATES

    return next((p for p in FONT_CANDIDATES + ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"] if os.path.exists(p)), None)


def test_render_card_single_image(tmp_path):
    font = _font()
    if not font:
        pytest.skip("한글 폰트 없음")
    from PIL import Image

    d = NewsDraft("북한 “저고도 비행 궤도 변경 능력 보유”", ["a"], "c", [], "https://x", badge="속보", kicker="합참 발표", subhead="‘AI 도입’ 상기 필요", source_name="MBN")
    path = render_card(d, str(tmp_path), font, breaking=True)
    assert path.endswith("card.png") and Image.open(path).size == (1080, 1350)


def test_render_card_handles_very_long_headline_and_ai_label(tmp_path):
    font = _font()
    if not font:
        pytest.skip("한글 폰트 없음")
    from PIL import Image

    bg = tmp_path / "bg.png"
    Image.new("RGB", (1024, 1536), (30, 90, 160)).save(bg)
    d = NewsDraft("아주 긴 제목 " * 30, ["a"], "c", [], "https://x", subhead="부제 " * 60)
    path = render_card(d, str(tmp_path / "out"), font, str(bg), ai_label=True)
    assert Image.open(path).size == (1080, 1350)  # 넘쳐도 깨지지 않고 한 장으로 나온다


def test_outlet_name_from_domain():
    from insta_agent.outlets import outlet_name

    assert outlet_name("https://news.mbn.co.kr/view?x=1") == "MBN"
    assert outlet_name("https://www.imaeil.com/page/view/2026") == "매일신문"
    assert outlet_name("https://unknown.example.org/a") == "unknown.example.org"


def test_news_draft_new_fields_and_full_text():
    d = parse_news_draft(
        '{"badge":"단독","kicker":"금융보안원","headline":"은행 해킹","subhead":"AI 도구 흔적","bullets":["가","나"],"caption":"본문","hashtags":["x"],"image_prompt":"p"}',
        "http://l", "헤럴드경제",
    )
    assert (d.badge, d.kicker, d.subhead, d.source_name) == ("단독", "금융보안원", "AI 도구 흔적", "헤럴드경제")
    txt = d.full_text()
    assert "• 가" in txt and "출처: 헤럴드경제 http://l" in txt


def test_old_stored_draft_without_new_fields_still_loads():
    d = NewsDraft(**{"headline": "h", "bullets": ["b"], "caption": "c", "hashtags": [], "source_link": "l"})
    assert d.badge == "" and d.source_name == ""


def test_fetch_unsplash_saves_photo_triggers_download_and_returns_credit(tmp_path):
    from insta_agent.stock import fetch_unsplash

    calls = []

    class R:
        content = b"JPEGDATA"
        def raise_for_status(self): pass
        def json(self):
            return {"results": [{
                "urls": {"raw": "https://images.unsplash.com/photo-1?ixid=abc"},
                "links": {"download_location": "https://api.unsplash.com/photos/1/download?ixid=abc"},
                "user": {"name": "Jane Doe", "links": {"html": "https://unsplash.com/@jane"}},
            }]}

    class H:
        def get(self, url, headers=None, params=None, timeout=None):
            calls.append((url, params))
            return R()

    out = tmp_path / "bg.png"
    credit, location = fetch_unsplash(make_cfg(unsplash_key="k"), "missile launch sea", str(out), http=H())
    assert out.read_bytes() == b"JPEGDATA"
    assert "w=1080&h=1350&fit=crop" in calls[1][0]          # 카드 크기로 잘라 받기
    assert len(calls) == 2                                      # 검색 + 사진 받기뿐, 아직 집계는 호출하지 않는다
    assert location.endswith("/photos/1/download?ixid=abc")
    assert credit == "Jane Doe / Unsplash https://unsplash.com/@jane?utm_source=yoonsquads_news&utm_medium=referral"


def test_unsplash_credit_goes_into_caption_and_background_is_reused(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    fetched = []

    def fake_fetch(cfg, query, path):
        fetched.append(query)
        open(path, "wb").write(b"x")
        return "Jane / Unsplash http://u", "http://dl"

    seen = []
    monkeypatch.setattr(bot, "fetch_unsplash", fake_fetch)
    monkeypatch.setattr(bot, "render_card", lambda draft, out, font, bg, label, breaking: seen.append((bg, label)) or "card.png")
    cfg = make_cfg(photo_source="unsplash", unsplash_key="k")
    d1 = NewsDraft("h", ["b"], "c", [], "l", photo_query="bank atm")
    bot.make_cards(cfg, 7, d1)                       # 검토 때 한 번 받고
    assert "사진: Jane / Unsplash http://u" in d1.full_text()
    d2 = NewsDraft("h", ["b"], "c", [], "l", photo_query="bank atm")
    bot.make_cards(cfg, 7, d2, reuse=True)           # 승인 때는 다시 받지 않는다
    assert fetched == ["bank atm"] and d2.photo_credit == "Jane / Unsplash http://u"
    assert all(label is False for _, label in seen)  # Unsplash 사진에는 'AI 생성' 표시를 달지 않는다


def test_legacy_ai_images_flag_still_means_ai(monkeypatch):
    from insta_agent.config import Config

    for k in ("PHOTO_SOURCE",):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AI_IMAGES", "true")
    assert Config.load().photo_source == "ai"
    monkeypatch.setenv("PHOTO_SOURCE", "unsplash")
    assert Config.load().photo_source == "unsplash"


def test_unsplash_download_tracked_only_on_approval(monkeypatch, tmp_path):
    from insta_agent.stock import track_download

    monkeypatch.chdir(tmp_path)
    tracked = []
    monkeypatch.setattr(bot, "fetch_unsplash", lambda cfg, q, path: (open(path, "wb").write(b"x") and None) or ("J / Unsplash", "http://dl"))
    monkeypatch.setattr(bot, "track_download", lambda cfg, loc: tracked.append(loc))
    monkeypatch.setattr(bot, "render_card", lambda *a, **k: "card.png")
    monkeypatch.setattr(bot, "upload_image", lambda cfg, p: "https://img/x")
    cfg = make_cfg(photo_source="unsplash", unsplash_key="k")
    q, tg = Queue(":memory:"), FakeTG()
    draft = NewsDraft("h", ["b"], "c", [], "l", photo_query="q").__dict__
    cid = q.add_candidate({"title": "t", "summary": "s", "link": "l", "pub_date": ""}, draft)
    bot.make_cards(cfg, cid, NewsDraft("h", ["b"], "c", [], "l", photo_query="q"))   # 검토 단계
    assert tracked == []                                                             # 폐기될 수도 있으니 아직 집계 안 함
    bot.approve(cfg, q, tg, cid)
    assert tracked == ["http://dl"]


def test_diversify_tags_drops_recent_keeps_brand_and_minimum():
    from insta_agent.content import diversify_tags

    assert diversify_tags(["a", "b", "c", "d", "e"], ["a", "B"], brand="브랜드") == ["c", "d", "e", "브랜드"]
    # 새 태그가 모자라면 덜 겹치는 순서가 아니라도 최소 개수까지 채운다
    out = diversify_tags(["a", "b", "c", "d"], ["a", "b", "c"], min_keep=3)
    assert len(out) == 3 and "d" in out
    # 계정 고유 태그는 겹쳐도 중복 없이 한 번만
    assert diversify_tags(["x", "브랜드", "y", "z", "w"], [], brand="브랜드").count("브랜드") == 1


def test_recent_styles_and_prompt_avoid_repeats(monkeypatch):
    from insta_agent import content

    q = Queue(":memory:")
    q.add_candidate({"link": "1", "title": "t"}, {"caption": "첫 줄 후크\n본문", "hashtags": ["정치", "예산"]})
    q.add_candidate({"link": "2", "title": "t"}, {})                    # 실패 기록은 제외
    q.update_candidate(q.add_candidate({"link": "3", "title": "t"}, {"caption": "폐기됨", "hashtags": ["x"]}), status="rejected")
    recent = q.recent_styles()
    assert recent == [{"tags": ["정치", "예산"], "hook": "첫 줄 후크"}]

    seen = {}
    def fake(cfg, system, user, max_tokens=1500):
        seen["user"] = user
        return '{"badge":"속보","headline":"h","subhead":"s","bullets":["b"],"caption":"c","hashtags":["정치","새태그1","새태그2","새태그3","새태그4"],"photo_query":"q","image_prompt":"p"}'
    monkeypatch.setattr(content, "complete", fake)
    d = content.generate_news_draft(make_cfg(brand_hashtag="나우이슈"), {"title": "t", "summary": "s", "link": "l"}, recent=recent)
    assert "쓰지 말 것)" in seen["user"] and "예산" in seen["user"] and "첫 줄 후크" in seen["user"]
    assert "정치" not in d.hashtags and d.hashtags[-1] == "나우이슈"
