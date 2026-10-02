from datetime import datetime, timedelta, timezone

import pytest

from insta_agent.agent import run_due
from insta_agent.content import CAPTION_LIMIT, parse_draft
from insta_agent.queue import Queue


class FakeClient:
    def __init__(self, fail_on=None):
        self.calls, self.fail_on = [], fail_on

    def publish(self, urls, caption):
        self.calls.append((urls, caption))
        if caption == self.fail_on:
            raise RuntimeError("boom")
        return f"m{len(self.calls)}"


def test_parse_draft_cleans_tags():
    d = parse_draft('설명 {"caption":"안녕","hashtags":["#a","b c","a",""]} 끝')
    assert d.hashtags == ["a", "bc"]
    assert d.full_text() == "안녕\n\n#a #bc"


def test_parse_draft_truncates():
    d = parse_draft('{"caption":"%s","hashtags":["x"]}' % ("가" * 3000))
    assert len(d.full_text()) <= CAPTION_LIMIT


def test_parse_draft_rejects_non_json():
    with pytest.raises(ValueError):
        parse_draft("죄송합니다")


def test_queue_only_returns_due_pending():
    q = Queue(":memory:")
    now = datetime.now(timezone.utc)
    past = q.add("p", ["u"], now - timedelta(minutes=1))
    q.add("f", ["u"], now + timedelta(hours=1))
    assert [p.id for p in q.due()] == [past]


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        Queue(":memory:").add("x", ["u"], datetime(2026, 1, 1))


def test_run_due_isolates_failures():
    q = Queue(":memory:")
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    bad, good = q.add("bad", ["u"], past), q.add("good", ["u"], past)
    out = dict(run_due(q, FakeClient(fail_on="bad")))
    assert out[bad].startswith("failed") and out[good].startswith("published")
    assert {p.id: p.status for p in q.list()} == {bad: "failed", good: "published"}


def test_dry_run_does_not_publish():
    q = Queue(":memory:")
    q.add("x", ["u"], datetime.now(timezone.utc) - timedelta(minutes=1))
    c = FakeClient()
    run_due(q, c, dry_run=True)
    assert c.calls == [] and q.list()[0].status == "pending"
