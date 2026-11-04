from __future__ import annotations

import base64
from unittest.mock import MagicMock

import pytest

from email_telegram_bot.gmail.parser import EmailMessage
from email_telegram_bot.services.code_requests import (
    DEFAULT_CODE_PATTERN,
    FALLBACK_CODE_PATTERNS,
    CodeRequestService,
    UnknownServiceError,
)

HELLO_DATA = base64.urlsafe_b64encode(b"Codigo 123456").decode()


def _message(gmail_id="m1"):
    return {
        "id": gmail_id,
        "internalDate": "1762200000000",
        "payload": {
            "headers": [
                {"name": "From", "value": f"Alice <{gmail_id}@empresa.com>"},
                {"name": "To", "value": "bob@empresa.com"},
                {"name": "Subject", "value": "Report"},
            ],
            "parts": [{"mimeType": "text/plain", "body": {"data": HELLO_DATA}}],
        },
    }


def _gmail_returning(message):
    gmail = MagicMock()
    gmail.find_latest_message.return_value = message
    return gmail


def test_aliases_are_sorted_and_lowercased():
    service = CodeRequestService(
        MagicMock(), {"Disney": "b@x.com", "netflix": "a@x.com"}
    )

    assert service.aliases() == ["disney", "netflix"]


def test_find_latest_returns_parsed_email():
    gmail = _gmail_returning(_message("m1"))
    service = CodeRequestService(gmail, {"netflix": "m1@empresa.com"})

    email = service.find_latest("Netflix")

    assert email is not None
    assert email.gmail_id == "m1"
    assert email.body == "Codigo 123456"
    gmail.find_latest_message.assert_called_once_with("m1@empresa.com")


def test_find_latest_without_messages_returns_none():
    service = CodeRequestService(_gmail_returning(None), {"netflix": "a@x.com"})

    assert service.find_latest("netflix") is None


def test_unknown_alias_raises_with_available_list():
    service = CodeRequestService(_gmail_returning(None), {"netflix": "a@x.com"})

    with pytest.raises(UnknownServiceError, match="Unknown service 'disney'"):
        service.find_latest("disney")


def test_default_code_pattern_is_used_when_service_has_no_fallback():
    service = CodeRequestService(MagicMock(), {"netflix": "a@x.com"})

    assert service.code_pattern("netflix") == DEFAULT_CODE_PATTERN


def test_builtin_fallback_pattern_is_used_per_alias():
    service = CodeRequestService(MagicMock(), {"hbo": "a@x.com"})

    assert service.code_pattern("hbo") == FALLBACK_CODE_PATTERNS["hbo"]


def test_unknown_alias_falls_back_to_default_pattern():
    service = CodeRequestService(MagicMock(), {"netflix": "a@x.com"})

    assert service.code_pattern("not-a-service") == DEFAULT_CODE_PATTERN
