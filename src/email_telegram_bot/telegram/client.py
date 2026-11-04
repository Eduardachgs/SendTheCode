from __future__ import annotations

import logging

import requests

API_BASE_URL = "https://api.telegram.org"
DEFAULT_LONG_POLL_TIMEOUT = 25


class TelegramError(Exception):
    pass


class TelegramClient:
    def __init__(
        self,
        bot_token: str,
        timeout: float = 15.0,
        api_base_url: str = API_BASE_URL,
    ) -> None:
        self._timeout = timeout
        self._api_base_url = api_base_url
        self._bot_token = bot_token

    def _url(self, method: str) -> str:
        return f"{self._api_base_url}/bot{self._bot_token}/{method}"

    def deliver(self, chat_id: int | str, text: str) -> None:
        for chunk in split_text(text):
            self.send_message(chat_id, chunk)

    def send_message(self, chat_id: int | str, text: str) -> None:
        payload = {"chat_id": chat_id, "text": text}
        try:
            response = requests.post(self._url("sendMessage"), json=payload, timeout=self._timeout)
        except requests.RequestException as exc:
            raise TelegramError(f"Failed to reach Telegram API: {exc}") from exc
        self._check_response(response)

    def get_updates(
        self, offset: int = 0, timeout: int = DEFAULT_LONG_POLL_TIMEOUT
    ) -> list[dict]:
        params = {"offset": offset, "timeout": timeout}
        try:
            response = requests.get(
                self._url("getUpdates"),
                params=params,
                timeout=self._timeout + timeout,
            )
        except requests.RequestException as exc:
            raise TelegramError(f"Failed to reach Telegram API: {exc}") from exc
        data = self._check_response(response)
        return list(data.get("result", []))

    def _check_response(self, response: requests.Response) -> dict:
        try:
            data = response.json()
            ok = bool(data.get("ok"))
            description = data.get("description", "")
        except ValueError:
            ok = response.ok
            description = response.text[:200]
            data = {}

        if not ok:
            raise TelegramError(
                f"Telegram API returned an error "
                f"(HTTP {response.status_code}): {description}"
            )
        return data


def split_text(text: str, max_length: int = 4096) -> list[str]:
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        chunk = remaining[:max_length]
        if len(remaining) > max_length:
            boundary = max(chunk.rfind("\n"), chunk.rfind(". "), chunk.rfind(" "))
            if boundary > 0:
                chunk = chunk[:boundary]
        stripped = chunk.rstrip()
        if stripped:
            chunks.append(stripped)
        remaining = remaining[len(chunk):].lstrip()
    return chunks or [text[:max_length]]
