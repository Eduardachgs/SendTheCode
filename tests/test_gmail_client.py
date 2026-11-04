from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from email_telegram_bot.gmail.client import GmailClient


def _responses(search: dict, messages: list[dict]) -> MagicMock:
    service = MagicMock()
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = search
    service.users.return_value.messages.return_value.get.return_value.execute.side_effect = list(
        messages
    )
    return service


def test_pick_newest_when_search_order_is_unknown():
    newest = {"id": "new", "internalDate": "1700005000000", "payload": {}}
    middle = {"id": "mid", "internalDate": "1700002000000", "payload": {}}
    oldest = {"id": "old", "internalDate": "1700000000000", "payload": {}}
    search_result = {"messages": [{"id": "old"}, {"id": "new"}, {"id": "mid"}]}

    service = _responses(search_result, [oldest, newest, middle])
    latest = GmailClient(service).find_latest_message("alice@empresa.com")

    assert latest == newest


def test_search_without_results_returns_none():
    service = _responses({"messages": []}, [])

    assert GmailClient(service).find_latest_message("alice@empresa.com") is None


def test_missing_search_results_key_returns_none():
    service = _responses({}, [])

    assert GmailClient(service).find_latest_message("alice@empresa.com") is None


def test_search_query_and_limit_are_passed():
    service = _responses({"messages": []}, [])

    GmailClient(service).find_latest_message("alice@empresa.com")

    service.users.return_value.messages.return_value.list.assert_called_once_with(
        userId="me", q="from:alice@empresa.com", maxResults=5
    )


def test_http_error_is_wrapped_into_gmail_error():
    service = MagicMock()
    service.users.return_value.messages.return_value.list.return_value.execute.side_effect = HttpError(
        MagicMock(status_code=503), b"{}"
    )

    with pytest.raises(Exception, match="Gmail search failed"):
        GmailClient(service).find_latest_message("alice@empresa.com")


def test_only_fetches_capped_number_of_candidates():
    search_result = {"messages": [{"id": str(i)} for i in range(10)]}
    fetched: list[str] = []

    service = MagicMock()
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = search_result

    def _get_recorder(**kwargs):
        fetched.append(kwargs["id"])
        recorder = MagicMock()
        recorder.execute.return_value = {
            "id": kwargs["id"],
            "internalDate": "0",
            "payload": {},
        }
        return recorder

    service.users.return_value.messages.return_value.get.side_effect = _get_recorder

    GmailClient(service).find_latest_message("a@x.com")

    assert len(fetched) == 5
    assert set(fetched) == {"0", "1", "2", "3", "4"}
