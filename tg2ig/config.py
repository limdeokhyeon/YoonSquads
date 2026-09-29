import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"환경변수 {name} 가 설정되지 않았습니다. .env 파일을 확인하세요.")
    return value


@dataclass(frozen=True)
class Config:
    telegram_token: str
    allowed_user_ids: frozenset[int]
    ig_user_id: str
    ig_access_token: str
    public_base_url: str
    graph_version: str = "v21.0"
    media_dir: Path = field(default_factory=lambda: Path("media"))
    media_port: int = 8080


def load_config() -> Config:
    allowed = {
        int(x) for x in os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").split(",") if x.strip()
    }
    if not allowed:
        raise RuntimeError(
            "TELEGRAM_ALLOWED_USER_IDS 가 비어 있습니다. 게시 권한이 있는 텔레그램 사용자 ID를 넣으세요."
        )
    return Config(
        telegram_token=_require("TELEGRAM_BOT_TOKEN"),
        allowed_user_ids=frozenset(allowed),
        ig_user_id=_require("INSTAGRAM_USER_ID"),
        ig_access_token=_require("INSTAGRAM_ACCESS_TOKEN"),
        public_base_url=_require("PUBLIC_BASE_URL").rstrip("/"),
        graph_version=os.environ.get("INSTAGRAM_GRAPH_VERSION", "v21.0"),
        media_dir=Path(os.environ.get("MEDIA_DIR", "media")),
        media_port=int(os.environ.get("MEDIA_PORT", "8080")),
    )
