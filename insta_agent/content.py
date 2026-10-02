"""Claude로 인스타그램 캡션·해시태그를 생성한다."""
import json
from dataclasses import dataclass

import anthropic

from .config import Config

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


def generate_draft(cfg: Config, topic: str, extra: str = "") -> Draft:
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    msg = client.messages.create(
        model=cfg.model,
        max_tokens=1500,
        system=SYSTEM.format(limit=CAPTION_LIMIT - 400),
        messages=[
            {
                "role": "user",
                "content": f"주제: {topic}\n브랜드 톤: {cfg.brand_voice}\n추가 요청: {extra or '없음'}",
            }
        ],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    return parse_draft(text)


NEWS_SYSTEM = """당신은 인스타그램 뉴스 카드 에디터입니다.
기사의 제목과 검색 요약만 주어집니다. 이를 바탕으로 카드뉴스를 직접 새로 작성하세요.
규칙:
- 기사 문장을 그대로 옮기지 말고 자신의 표현으로 쓸 것. 주어진 정보에 없는 사실은 추가 금지
- headline: 표지 제목 28자 이내
- bullets: 핵심 3개, 각 45자 이내
- caption: 후크 한 줄 + 쉬운 해설 + 마지막에 행동 유도 한 줄 (출처는 시스템이 따로 붙이므로 쓰지 말 것)
- hashtags: '#' 없이 8~12개
- 의료·건강 내용은 단정하지 말고 "전문가 상담 권장" 톤 유지
반드시 JSON만 출력: {"headline": str, "bullets": [str], "caption": str, "hashtags": [str]}"""


@dataclass
class NewsDraft:
    headline: str
    bullets: list[str]
    caption: str
    hashtags: list[str]
    source_link: str

    def full_text(self) -> str:
        tags = " ".join(f"#{t}" for t in self.hashtags)
        return f"{self.caption}\n\n출처: {self.source_link}\n\n{tags}".strip()


def parse_news_draft(raw: str, source_link: str) -> NewsDraft:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON 응답이 아닙니다: {raw[:100]}")
    d = json.loads(raw[start : end + 1])
    base = parse_draft(json.dumps({"caption": d["caption"], "hashtags": d.get("hashtags", [])}))
    bullets = [str(b).strip() for b in d["bullets"] if str(b).strip()][:4]
    if not bullets:
        raise ValueError("bullets가 비어 있습니다")
    return NewsDraft(str(d["headline"]).strip(), bullets, base.caption, base.hashtags, source_link)


def generate_news_draft(cfg: Config, item: dict, feedback: str = "") -> NewsDraft:
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    msg = client.messages.create(
        model=cfg.model,
        max_tokens=1500,
        system=NEWS_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"제목: {item['title']}\n검색 요약: {item['summary']}\n"
                f"브랜드 톤: {cfg.brand_voice}\n수정 요청: {feedback or '없음'}",
            }
        ],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    return parse_news_draft(text, item["link"])
