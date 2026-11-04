from __future__ import annotations

import re
from typing import Mapping

from ..gmail.client import GmailClient
from ..gmail.parser import EmailMessage, parse_message

DEFAULT_CODE_PATTERN = r"\d{4,8}"

FALLBACK_CODE_PATTERNS: Mapping[str, str] = {
    "hbo": r"Seu código único\s*-+\s*(\d{6})",
}


class UnknownServiceError(Exception):
    def __init__(self, alias: str, available: list[str]) -> None:
        self.alias = alias
        self.available = available
        super().__init__(
            f"Unknown service {alias!r}; available: {', '.join(available)}"
        )


class CodeRequestService:
    def __init__(
        self,
        gmail_client: GmailClient,
        service_senders: Mapping[str, str],
    ) -> None:
        self._gmail = gmail_client
        self._services = {
            alias.strip().lower(): sender
            for alias, sender in service_senders.items()
        }

    def aliases(self) -> list[str]:
        return sorted(self._services)

    def code_pattern(self, alias: str) -> str:
        normalized = self._normalize(alias)
        return FALLBACK_CODE_PATTERNS.get(normalized, DEFAULT_CODE_PATTERN)

    def find_latest(self, alias: str) -> EmailMessage | None:
        alias_normalized = self._normalize(alias)
        sender = self._services.get(alias_normalized)
        if sender is None:
            raise UnknownServiceError(alias_normalized, self.aliases())

        message = self._gmail.find_latest_message(sender)
        if message is None:
            return None
        return parse_message(message.get("id", ""), message)

    def _normalize(self, alias: str) -> str:
        return alias.strip().lower()
