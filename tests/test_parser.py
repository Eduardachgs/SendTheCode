from __future__ import annotations

import base64

import pytest

from email_telegram_bot.gmail.parser import EmailMessage, parse_message

B64 = base64.urlsafe_b64encode


def _message(**overrides):
    payload = {
        "headers": [
            {"name": "From", "value": "Alice <alice@empresa.com>"},
            {"name": "To", "value": "bob@empresa.com"},
            {"name": "Cc", "value": "carol@empresa.com"},
            {"name": "Subject", "value": "Monthly report"},
        ],
        "parts": [
            {"mimeType": "text/plain", "body": {"data": B64(b"Hello from Alice").decode()}},
            {"mimeType": "text/html", "body": {"data": B64(b"<p>Hello from Alice</p>").decode()}},
        ],
    }
    if "parts" in overrides or "headers" in overrides:
        if "parts" in overrides:
            payload["parts"] = overrides.pop("parts")
        if "headers" in overrides:
            payload["headers"] = overrides.pop("headers")
    message = {"internalDate": "1700000000000", "payload": payload}
    message.update(overrides)
    return message


def test_plain_text_is_prioritized():
    message = parse_message("abc123", _message())

    assert message.body == "Hello from Alice"


def test_html_fallback_is_stripped():
    message = parse_message(
        "abc123",
        _message(
            parts=[
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": B64(b"<p>hello</p><script>bad()</script>").decode()
                    },
                },
            ]
        ),
    )

    assert message.body == "hello"
    assert "bad()" not in message.body


def test_headers_and_sender_extraction():
    message = parse_message("abc123", _message())

    assert message.sender_name == "Alice"
    assert message.sender_email == "alice@empresa.com"
    assert message.recipients == "bob@empresa.com, carol@empresa.com"
    assert message.subject == "Monthly report"


def test_received_at_uses_internal_date():
    message = parse_message("abc123", _message())

    assert message.received_at.startswith("2023-11-14")
    assert "+00:00" in message.received_at


def test_encoded_subject_is_decoded():
    encoded = base64.b64encode("Oração".encode()).decode()
    message = parse_message(
        "abc123",
        _message(headers=[{"name": "Subject", "value": f"=?utf-8?b?{encoded}?="}]),
    )

    assert message.subject == "Oração"


def test_no_body_returns_empty_string():
    message = parse_message("abc123", _message(parts=[]))

    assert message.body == ""


def test_attachment_part_with_body_data_is_skipped():
    message = parse_message(
        "abc123",
        _message(
            parts=[
                {
                    "mimeType": "text/plain",
                    "filename": "report.txt",
                    "body": {"data": B64(b"not@thebody").decode()},
                },
            ]
        ),
    )

    assert message.body == ""


def test_nested_multipart_body_is_found():
    inner = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": B64(b"nested hello").decode()}},
        ],
    }
    message = parse_message("abc123", _message(parts=[inner]))

    assert message.body == "nested hello"


def test_email_message_is_frozen():
    message = parse_message("abc123", _message())

    with pytest.raises(Exception):
        message.subject = "changed"
