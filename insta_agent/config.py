from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


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
        )
