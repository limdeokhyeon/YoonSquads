from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _photo_source() -> str:
    """none(그라데이션) | ai(GPT 이미지) | unsplash(무료 사진). 예전 AI_IMAGES=true 설정도 인식한다."""
    src = os.getenv("PHOTO_SOURCE", "").lower()
    if src in ("none", "ai", "unsplash"):
        return src
    return "ai" if os.getenv("AI_IMAGES", "false").lower() in ("1", "true", "yes") else "none"


def _list(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    ig_user_id: str
    ig_access_token: str
    graph_version: str
    model: str
    brand_voice: str
    db_path: str
    naver_client_id: str
    naver_client_secret: str
    telegram_token: str
    telegram_chat_id: str
    news_keywords: list[str]
    daily_count: int
    collect_hour: int
    post_hours: list[int]
    imgbb_key: str
    font_path: str
    ai_label: bool
    photo_source: str
    unsplash_key: str
    openai_key: str
    openai_image_model: str
    fetch_body: bool
    breaking_enabled: bool
    breaking_keywords: list[str]
    breaking_poll_minutes: int
    breaking_max_per_day: int
    breaking_max_age_min: int

    @classmethod
    def load(cls) -> "Config":
        load_dotenv()
        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            ig_user_id=os.getenv("IG_USER_ID", ""),
            ig_access_token=os.getenv("IG_ACCESS_TOKEN", ""),
            graph_version=os.getenv("IG_GRAPH_VERSION", "v21.0"),
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"),
            brand_voice=os.getenv("BRAND_VOICE", "친근하고 따뜻한 말투"),
            db_path=os.getenv("DB_PATH", "queue.db"),
            naver_client_id=os.getenv("NAVER_CLIENT_ID", ""),
            naver_client_secret=os.getenv("NAVER_CLIENT_SECRET", ""),
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            news_keywords=_list("NEWS_KEYWORDS", "임신,육아"),
            daily_count=int(os.getenv("DAILY_COUNT", "3")),
            collect_hour=int(os.getenv("COLLECT_HOUR", "9")),
            post_hours=[int(h) for h in _list("POST_HOURS", "12,18,21")],
            imgbb_key=os.getenv("IMGBB_API_KEY", ""),
            font_path=os.getenv("FONT_PATH", ""),
            breaking_enabled=os.getenv("BREAKING", "false").lower() in ("1", "true", "yes"),
            breaking_keywords=_list("BREAKING_KEYWORDS", "속보"),
            breaking_poll_minutes=int(os.getenv("BREAKING_POLL_MINUTES", "5")),
            breaking_max_per_day=int(os.getenv("BREAKING_MAX_PER_DAY", "5")),
            breaking_max_age_min=int(os.getenv("BREAKING_MAX_AGE_MIN", "90")),
            fetch_body=os.getenv("FETCH_BODY", "false").lower() in ("1", "true", "yes"),
            ai_label=os.getenv("AI_LABEL", "true").lower() in ("1", "true", "yes"),
            photo_source=_photo_source(),
            unsplash_key=os.getenv("UNSPLASH_ACCESS_KEY", ""),
            openai_key=os.getenv("OPENAI_API_KEY", ""),
            openai_image_model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        )


def update_env(key: str, value: str, path: str = ".env") -> None:
    """.env의 `key=` 줄을 바꾸고, 없으면 추가한다."""
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
