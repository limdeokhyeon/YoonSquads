"""Instagram Graph API 콘텐츠 게시 클라이언트.

이미지는 공개 접근 가능한 URL이어야 한다(로컬 파일 직접 업로드 불가).
"""

from __future__ import annotations

import time

import requests

from .config import Config
from .safety import redact

RETRY_DELAYS = (2, 5, 10)  # 일시적 오류는 이 간격(초)으로 최대 3번 더 시도
_sleep = time.sleep


class InstagramError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, code: int | None = None, ambiguous: bool = False):
        super().__init__(message)
        self.status, self.code = status, code
        # True면 "요청은 갔는데 결과를 모른다": 이미 올라갔을 수 있어 자동으로 다시 시도하면 안 된다
        self.ambiguous = ambiguous


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

    def publishing_limit(self) -> dict:
        """게시 권한 점검용(읽기 전용): 권한이 없으면 오류가 난다. 24시간 게시 한도 사용량도 보여 준다."""
        data = self._call("GET", f"{self.user}/content_publishing_limit", fields="quota_usage,config")
        item = (data.get("data") or [{}])[0]
        return {"quota_usage": item.get("quota_usage"), "quota_total": (item.get("config") or {}).get("quota_total")}

    METRICS = ("views", "reach", "likes", "comments", "saved", "shares", "total_interactions")

    @staticmethod
    def _parse_insights(data: dict) -> dict:
        out = {}
        for item in data.get("data", []):
            values = item.get("values") or []
            value = values[0].get("value") if values else (item.get("total_value") or {}).get("value")
            if isinstance(value, (int, float)):
                out[item["name"]] = value
        return out

    def media_insights(self, media_id: str) -> dict:
        """게시물 성과(조회·도달·좋아요·댓글·저장·공유). 일부 지표가 미지원이면 하나씩 시도해 가능한 것만 모은다.

        권한이 없으면(instagram_business_manage_insights) InstagramError 가 난다."""
        try:
            return self._parse_insights(self._call("GET", f"{media_id}/insights", metric=",".join(self.METRICS)))
        except InstagramError as first:
            out, last = {}, first
            for m in self.METRICS:
                try:
                    out.update(self._parse_insights(self._call("GET", f"{media_id}/insights", metric=m)))
                except InstagramError as e:
                    last = e
            if not out:
                raise last
            return out

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

    def _call(self, method: str, path: str, retry: bool = True, **params) -> dict:
        """API 호출. retry=True면 연결 실패·5xx·일시적 오류(code 1,2)를 몇 번 더 시도한다(되풀이해도 안전한 호출만)."""
        params["access_token"] = self.token
        delays = (0,) + RETRY_DELAYS if retry else (0,)
        last: Exception | None = None
        for delay in delays:
            if delay:
                _sleep(delay)
            try:
                resp = self.http.request(method, f"{self.base}/{path}", params=params, timeout=30)
            except requests.RequestException as e:
                if not retry:
                    raise
                last = e
                continue
            try:
                data = resp.json()
            except ValueError:
                data = {}
            if resp.status_code >= 400 or "error" in data:
                err = data.get("error", {})
                exc = InstagramError(
                    f"{err.get('message') or resp.text[:200]} (code={err.get('code')})", status=resp.status_code, code=err.get("code")
                )
                if retry and (resp.status_code >= 500 or err.get("code") in (1, 2)):
                    last = exc
                    continue
                raise exc
            return data
        if isinstance(last, InstagramError):
            raise last
        raise InstagramError(f"연결 실패: {redact(last)}")

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
        try:
            # 발행 요청은 자동으로 되풀이하지 않는다: 응답만 못 받았을 뿐 이미 올라갔다면 같은 글이 두 번 올라가므로
            return self._call("POST", f"{self.user}/media_publish", retry=False, creation_id=container_id)["id"]
        except requests.RequestException as e:
            raise InstagramError(f"발행 응답을 받지 못했습니다: {redact(e)}", ambiguous=True)
        except InstagramError as e:
            if e.status is not None and e.status >= 500:
                e.ambiguous = True
            raise

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
