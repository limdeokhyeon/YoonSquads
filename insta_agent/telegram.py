"""텔레그램 Bot API 최소 클라이언트. 지정된 chat id의 요청만 처리한다."""

from __future__ import annotations

import json

import requests


class Telegram:
    def __init__(self, token: str, chat_id: str, http=requests):
        self.chat_id = str(chat_id)
        self.base = f"https://api.telegram.org/bot{token}"
        self.http = http

    def _call(self, method: str, timeout: int = 30, **data) -> dict:
        resp = self.http.post(f"{self.base}/{method}", data=data, timeout=timeout)
        body = resp.json()
        if not body.get("ok"):
            raise RuntimeError(f"Telegram {method} 실패: {body.get('description')}")
        return body["result"]

    def send(self, text: str, buttons: list[tuple[str, str]] | None = None) -> None:
        data = {"chat_id": self.chat_id, "text": text[:4000], "disable_web_page_preview": "true"}
        if buttons:
            data["reply_markup"] = json.dumps({"inline_keyboard": [[{"text": t, "callback_data": c} for t, c in buttons]]})
        self._call("sendMessage", **data)

    def send_photo(self, path: str, caption: str = "") -> None:
        with open(path, "rb") as f:
            resp = self.http.post(
                f"{self.base}/sendPhoto",
                data={"chat_id": self.chat_id, "caption": caption[:1000]},
                files={"photo": f},
                timeout=60,
            )
        if not resp.json().get("ok"):
            raise RuntimeError(f"Telegram sendPhoto 실패: {resp.text[:200]}")

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        self._call("answerCallbackQuery", callback_query_id=callback_id, text=text)

    def get_updates(self, offset: int | None = None, timeout: int = 25) -> list[dict]:
        data = {"timeout": timeout, "allowed_updates": json.dumps(["message", "callback_query"])}
        if offset is not None:
            data["offset"] = offset
        return self._call("getUpdates", timeout=timeout + 10, **data)

    def is_owner(self, update: dict) -> bool:
        msg = update.get("message") or (update.get("callback_query") or {}).get("message") or {}
        sender = (update.get("message") or update.get("callback_query") or {}).get("from", {})
        return str(msg.get("chat", {}).get("id")) == self.chat_id and str(sender.get("id")) == self.chat_id
