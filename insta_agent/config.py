import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    ig_user_id: str
    ig_access_token: str
    graph_version: str
    model: str
    brand_voice: str
    db_path: str

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
        )
