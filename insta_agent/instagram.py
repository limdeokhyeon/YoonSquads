"""Instagram Graph API 콘텐츠 게시 클라이언트.

이미지는 공개 접근 가능한 URL이어야 한다(로컬 파일 직접 업로드 불가).
"""
import time

import requests

from .config import Config


class InstagramError(RuntimeError):
    pass


class InstagramClient:
    def __init__(self, cfg: Config, session: requests.Session | None = None):
        self.cfg = cfg
        self.http = session or requests.Session()
        self.base = f"https://graph.facebook.com/{cfg.graph_version}"

    def _call(self, method: str, path: str, **params) -> dict:
        params["access_token"] = self.cfg.ig_access_token
        resp = self.http.request(method, f"{self.base}/{path}", params=params, timeout=30)
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            raise InstagramError(f"{err.get('message', resp.text)} (code={err.get('code')})")
        return data

    def _create_container(self, **params) -> str:
        return self._call("POST", f"{self.cfg.ig_user_id}/media", **params)["id"]

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
        return self._call("POST", f"{self.cfg.ig_user_id}/media_publish", creation_id=container_id)["id"]

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
