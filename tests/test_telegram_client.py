from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from email_telegram_bot.telegram.client import TelegramClient, TelegramError, split_text


def _response(ok=True, status_code=200, description="ok"):
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.text = json.dumps({"ok": ok, "description": description})
    response.json.return_value = {"ok": ok, "description": description}
    return response


@patch("email_telegram_bot.telegram.client.requests.post")
def test_send_message_posts_to_correct_url_and_payload(post):
    client = TelegramClient("TOKEN")

    post.return_value = _response(ok=True)
    client.send_message(42, "hello")

    args, kwargs = post.call_args
    assert args[0] == "https://api.telegram.org/botTOKEN/sendMessage"
    assert kwargs["json"] == {"chat_id": 42, "text": "hello"}


@patch("email_telegram_bot.telegram.client.requests.post")
def test_send_message_raises_on_ko_response(post):
    client = TelegramClient("TOKEN")

    post.return_value = _response(ok=False, status_code=400, description="chat not found")

    with pytest.raises(TelegramError, match="chat not found"):
        client.send_message(42, "hello")


@patch("email_telegram_bot.telegram.client.requests.post")
def test_send_message_wraps_network_errors(post):
    client = TelegramClient("TOKEN")

    post.side_effect = requests.ConnectionError("no internet")

    with pytest.raises(TelegramError, match="Failed to reach Telegram API"):
        client.send_message(42, "hello")


@patch("email_telegram_bot.telegram.client.requests.post")
def test_deliver_splits_large_text(post):
    post.return_value = _response(ok=True)
    client = TelegramClient("TOKEN")

    text = "x" * 9000
    client.deliver(42, text)

    assert post.call_count == len(split_text(text))
    assert post.call_count > 1


@patch("email_telegram_bot.telegram.client.requests.get")
def test_get_updates_posts_with_offset_and_timeout(get):
    client = TelegramClient("TOKEN")

    get.return_value = _response(ok=True)
    get.return_value.json.return_value = {
        "ok": True,
        "result": [{"update_id": 7, "message": {}}],
    }
    updates = client.get_updates(offset=5)

    args, kwargs = get.call_args
    assert args[0] == "https://api.telegram.org/botTOKEN/getUpdates"
    assert kwargs["params"] == {"offset": 5, "timeout": 25}
    assert updates == [{"update_id": 7, "message": {}}]


@patch("email_telegram_bot.telegram.client.requests.get")
def test_get_updates_raises_on_ko_response(get):
    client = TelegramClient("TOKEN")

    get.return_value = _response(ok=False, status_code=401, description="Unauthorized")

    with pytest.raises(TelegramError, match="Unauthorized"):
        client.get_updates()


@patch("email_telegram_bot.telegram.client.requests.get")
def test_get_updates_wraps_network_errors(get):
    client = TelegramClient("TOKEN")

    get.side_effect = requests.ReadTimeout("slow network")

    with pytest.raises(TelegramError, match="Failed to reach Telegram API"):
        client.get_updates()


@patch("email_telegram_bot.telegram.client.requests.post")
def test_non_json_response_uses_http_status(post):
    client = TelegramClient("TOKEN")

    post.return_value = MagicMock(spec=requests.Response, status_code=502)
    post.return_value.json.side_effect = ValueError("not json")
    post.return_value.text = "bad gateway"
    post.return_value.ok = False

    with pytest.raises(TelegramError):
        client.send_message(42, "hello")
