import asyncio

import httpx


class InstagramError(RuntimeError):
    pass


class InstagramClient:
    """Instagram API with Instagram Login 콘텐츠 게시 (비즈니스/크리에이터 계정 전용)."""

    def __init__(self, ig_user_id: str, access_token: str, version: str = "v21.0"):
        self._ig_user_id = ig_user_id
        self._token = access_token
        self._base = f"https://graph.instagram.com/{version}"
        self._http = httpx.AsyncClient(timeout=30)

    async def _request(self, method: str, path: str, **params) -> dict:
        params["access_token"] = self._token
        resp = await self._http.request(method, f"{self._base}/{path}", params=params)
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            msg = data.get("error", {}).get("message", resp.text)
            raise InstagramError(msg)
        return data

    async def publish_photo(self, image_url: str, caption: str = "") -> str:
        """공개 접근 가능한 JPEG URL을 게시하고 게시물 ID를 반환."""
        container = await self._request(
            "POST", f"{self._ig_user_id}/media", image_url=image_url, caption=caption
        )
        creation_id = container["id"]
        await self._wait_until_ready(creation_id)
        published = await self._request(
            "POST", f"{self._ig_user_id}/media_publish", creation_id=creation_id
        )
        return published["id"]

    async def _wait_until_ready(self, creation_id: str, attempts: int = 10) -> None:
        for _ in range(attempts):
            status = (await self._request("GET", creation_id, fields="status_code"))["status_code"]
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"미디어 처리 실패: {status}")
            await asyncio.sleep(2)
        raise InstagramError("미디어 처리 시간이 초과되었습니다.")

    async def permalink(self, media_id: str) -> str | None:
        data = await self._request("GET", media_id, fields="permalink")
        return data.get("permalink")

    async def aclose(self) -> None:
        await self._http.aclose()
