"""Instagram Graph API 콘텐츠 게시 클라이언트.

이미지는 공개 접근 가능한 URL이어야 한다(로컬 파일 직접 업로드 불가).
"""

from __future__ import annotations

import time

import requests

from .config import Config


class InstagramError(RuntimeError):
    pass


def api_host(token: str) -> str:
    """`IGAA...` 토큰(Instagram 로그인)은 graph.instagram.com, `EAA...`(Facebook 로그인)는 graph.facebook.com."""
    return "graph.instagram.com" if token.startswith("IG") else "graph.facebook.com"


class InstagramClient:
    def __init__(self, cfg: Config, session: requests.Session | None = None):
        self.cfg = cfg
        self.http = session or requests.Session()
        self.token = cfg.ig_access_token
        self.host = api_host(self.token)
        self.base = f"https://{self.host}/{cfg.graph_version}"
        # Instagram 로그인 토큰은 `me`로 내 계정을 가리킬 수 있어 ID를 비워 둬도 된다
        self.user = cfg.ig_user_id or ("me" if self.host == "graph.instagram.com" else "")

    def whoami(self) -> dict:
        """토큰이 유효한지, 어느 계정인지 확인한다."""
        if self.host == "graph.instagram.com":
            return self._call("GET", "me", fields="user_id,username")
        return self._call("GET", self.user, fields="username")

    def refresh_token(self) -> tuple[str, int]:
        """장기 토큰(60일)을 연장한다. 발급 24시간 후부터 만료 전까지 가능. (새 토큰, 유효 초) 반환."""
        if self.host != "graph.instagram.com":
            raise InstagramError("자동 갱신은 Instagram 로그인 토큰(IGAA...)만 지원합니다")
        resp = self.http.get(
            "https://graph.instagram.com/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": self.token},
            timeout=30,
        )
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            raise InstagramError(data.get("error", {}).get("message", resp.text))
        self.token = data["access_token"]
        return self.token, int(data.get("expires_in", 0))

    def _call(self, method: str, path: str, **params) -> dict:
        params["access_token"] = self.token
        resp = self.http.request(method, f"{self.base}/{path}", params=params, timeout=30)
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            raise InstagramError(f"{err.get('message', resp.text)} (code={err.get('code')})")
        return data

    def _create_container(self, **params) -> str:
        return self._call("POST", f"{self.user}/media", **params)["id"]

    def _wait_ready(self, container_id: str, tries: int = 20, delay: float = 3.0) -> None:
        for _ in range(tries):
            status = self._call("GET", container_id, fields="status_code")["status_code"]
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"컨테이너 처리 실패: {status}")
            time.sleep(delay)
        raise InstagramError("컨테이너 처리 시간 초과")

    def _publish(self, container_id: str) -> str:
        self._wait_ready(container_id)
        return self._call("POST", f"{self.user}/media_publish", creation_id=container_id)["id"]

    def publish_image(self, image_url: str, caption: str) -> str:
        return self._publish(self._create_container(image_url=image_url, caption=caption))

    def publish_carousel(self, image_urls: list[str], caption: str) -> str:
        if not 2 <= len(image_urls) <= 10:
            raise InstagramError("캐러셀은 이미지 2~10장이 필요합니다")
        children = [self._create_container(image_url=u, is_carousel_item="true") for u in image_urls]
        for c in children:
            self._wait_ready(c)
        parent = self._create_container(
            media_type="CAROUSEL", children=",".join(children), caption=caption
        )
        return self._publish(parent)

    def publish(self, image_urls: list[str], caption: str) -> str:
        if len(image_urls) == 1:
            return self.publish_image(image_urls[0], caption)
        return self.publish_carousel(image_urls, caption)
