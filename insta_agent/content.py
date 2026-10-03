"""Claude로 인스타그램 캡션·해시태그를 생성한다."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

import anthropic

from .article import longest_overlap
from .config import Config
from .outlets import outlet_name

CAPTION_LIMIT = 2200
HASHTAG_LIMIT = 30

SYSTEM = """당신은 인스타그램 콘텐츠 에디터입니다.
주제와 브랜드 톤을 받아 게시물 캡션과 해시태그를 만듭니다.
규칙:
- 첫 줄은 스크롤을 멈추게 하는 후크 문장
- 캡션 본문은 {limit}자 이내, 마지막에 행동 유도(CTA) 한 줄
- 해시태그는 '#' 없이 10~15개, 대형/중형/소형 태그를 섞을 것
- 과장·허위 정보, 의료·금융 효능 단정 표현 금지
반드시 JSON만 출력: {{"caption": str, "hashtags": [str]}}"""


@dataclass
class Draft:
    caption: str
    hashtags: list[str]

    def full_text(self) -> str:
        tags = " ".join(f"#{t}" for t in self.hashtags)
        return f"{self.caption}\n\n{tags}".strip()


def parse_draft(raw: str) -> Draft:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON 응답이 아닙니다: {raw[:100]}")
    data = json.loads(raw[start : end + 1])
    tags = [t.lstrip("#").replace(" ", "") for t in data.get("hashtags", [])]
    tags = list(dict.fromkeys(t for t in tags if t))[:HASHTAG_LIMIT]
    caption = str(data["caption"]).strip()
    draft = Draft(caption=caption, hashtags=tags)
    if len(draft.full_text()) > CAPTION_LIMIT:
        budget = CAPTION_LIMIT - len(" ".join(f"#{t}" for t in tags)) - 2
        draft.caption = caption[: max(budget, 0)].rstrip()
    return draft


def complete(cfg: Config, system: str, user: str, max_tokens: int = 1500) -> str:
    """API 키가 있으면 Anthropic API, 없으면 로그인된 Claude Code(`claude -p`)로 호출한다."""
    if cfg.anthropic_api_key:
        client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
        msg = client.messages.create(
            model=cfg.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")

    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("ANTHROPIC_API_KEY가 없고 claude 명령도 찾지 못했습니다")
    # 프로젝트 폴더(.env 등)를 읽지 못하도록 빈 임시 폴더에서 실행
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [claude, "-p", f"{system}\n\n---\n{user}"],
            capture_output=True, text=True, timeout=240, cwd=tmp,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p 실패: {(proc.stderr or proc.stdout)[:300]}")
    return proc.stdout


def generate_draft(cfg: Config, topic: str, extra: str = "") -> Draft:
    text = complete(
        cfg,
        SYSTEM.format(limit=CAPTION_LIMIT - 400),
        f"주제: {topic}\n브랜드 톤: {cfg.brand_voice}\n추가 요청: {extra or '없음'}",
    )
    return parse_draft(text)


NEWS_SYSTEM = """당신은 인스타그램 뉴스 카드 에디터입니다.
기사의 제목과 검색 요약(그리고 있으면 본문 발췌)이 주어집니다. 이를 바탕으로 카드를 직접 새로 작성하세요.
카드는 사진 한 장 위에 [배지] [작은 문구] 큰 제목 / 부제 / 출처 순으로 얹히는 한 장짜리 뉴스 카드입니다.
규칙:
- 기사 문장을 그대로 옮기지 말고 자신의 표현으로 쓸 것. 주어진 정보에 없는 사실은 추가 금지
- '본문 발췌'가 있으면 사실관계(누가·언제·무엇을·수치) 파악에만 쓰고, 문장은 어느 부분도 그대로 옮기지 말 것
- badge: 2~6자. 긴급 보도면 "속보", 독점 보도면 "단독", 그 외 "정치 이슈"·"경제 이슈"·"사회 이슈"처럼 분야를 표시
- kicker: 제목 위 작은 문구(주체·맥락, 예 "합참 발표"). 8자 이내, 마땅치 않으면 빈 문자열
- headline: 뉴스 헤드라인 문체, 26자 이내, 한 문장. 줄바꿈은 넣지 말 것
- subhead: 제목을 보충하는 핵심 사실, 두 줄 이내(60자 이내)
- bullets: 핵심 3개, 각 45자 이내 (캡션 본문에 쓰임)
- caption: 후크 한 줄 + 쉬운 해설 + 마지막에 행동 유도 한 줄 (출처는 시스템이 따로 붙이므로 쓰지 말 것)
- hashtags: '#' 없이 8~12개
- 정치·시사 기사는 중립을 지킬 것: 특정 정당·인물·진영을 편들거나 비난하는 표현, 추측·단정, 선동적 표현 금지. 기사에 나온 사실과 각 측의 입장을 구분해 서술
- 의료·건강·투자 관련 내용은 단정하지 말고 전문가 확인을 권하는 톤 유지
- image_prompt: 카드 배경 사진용 영어 설명 한 문장. 기사 주제를 보여 주는 사실적인 장면(사건 현장, 건물, 사물, 풍경, 기관 외관 등)으로, 위쪽 2/3에 피사체가 오고 아래쪽은 비교적 어둡고 단순하게. 기사에 실명 인물이 나오면 그 사람을 그리지 말고 연단과 마이크, 빈 의자, 건물, 깃발, 실루엣 같은 상징 장면으로 대신할 것. 글자·간판·로고·얼굴은 넣지 말 것
반드시 JSON만 출력: {"badge": str, "kicker": str, "headline": str, "subhead": str, "bullets": [str], "caption": str, "hashtags": [str], "image_prompt": str}"""


@dataclass
class NewsDraft:
    headline: str
    bullets: list[str]
    caption: str
    hashtags: list[str]
    source_link: str
    image_prompt: str = ""
    badge: str = ""
    kicker: str = ""
    subhead: str = ""
    source_name: str = ""

    def full_text(self) -> str:
        tags = " ".join(f"#{t}" for t in self.hashtags)
        points = "\n".join(f"• {b}" for b in self.bullets)
        return f"{self.caption}\n\n{points}\n\n출처: {self.source_name or '기사 원문'} {self.source_link}\n\n{tags}".strip()


def parse_news_draft(raw: str, source_link: str, source_name: str = "") -> NewsDraft:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON 응답이 아닙니다: {raw[:100]}")
    d = json.loads(raw[start : end + 1])
    base = parse_draft(json.dumps({"caption": d["caption"], "hashtags": d.get("hashtags", [])}))
    bullets = [str(b).strip() for b in d["bullets"] if str(b).strip()][:4]
    if not bullets:
        raise ValueError("bullets가 비어 있습니다")
    return NewsDraft(
        str(d["headline"]).strip(), bullets, base.caption, base.hashtags, source_link,
        image_prompt=str(d.get("image_prompt", "")).strip(), badge=str(d.get("badge", "")).strip(),
        kicker=str(d.get("kicker", "")).strip(), subhead=str(d.get("subhead", "")).strip(), source_name=source_name,
    )


OVERLAP_LIMIT = 25  # 원문과 연속 25자 이상 같으면 베낀 것으로 보고 다시 쓴다


def generate_news_draft(cfg: Config, item: dict, feedback: str = "") -> NewsDraft:
    body = item.get("body", "")

    def run(fb: str) -> NewsDraft:
        user = (
            f"제목: {item['title']}\n검색 요약: {item['summary']}\n"
            + (f"본문 발췌(참고용, 문장을 옮기지 말 것): {body}\n" if body else "")
            + f"브랜드 톤: {cfg.brand_voice}\n수정 요청: {fb or '없음'}"
        )
        return parse_news_draft(complete(cfg, NEWS_SYSTEM, user), item["link"], outlet_name(item.get("originallink") or item["link"]))

    draft = run(feedback)
    source = f"{item['summary']} {body}"
    mine = " ".join([draft.headline, draft.subhead, draft.caption, *draft.bullets])
    if longest_overlap(mine, source) >= OVERLAP_LIMIT:
        draft = run((feedback + " " if feedback else "") + "원문과 같은 표현이 있으니 모든 문장을 완전히 다른 표현으로 다시 써 줘")
    return draft
