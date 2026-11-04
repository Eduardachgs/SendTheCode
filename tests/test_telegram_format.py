from __future__ import annotations

import pytest

from email_telegram_bot.gmail.parser import EmailMessage
from email_telegram_bot.telegram.bot import format_reply
from email_telegram_bot.telegram.client import split_text


def _email(body="Hello"):
    return EmailMessage(
        gmail_id="abc",
        sender_name="Alice",
        sender_email="alice@empresa.com",
        recipients="bob@empresa.com",
        subject="Report",
        received_at="2026-11-02T10:00:00+00:00",
        body=body,
    )


def test_format_email_contains_metadata_and_body():
    formatted = format_reply("netflix", _email())

    assert "netflix" in formatted
    assert "Alice <alice@empresa.com>" in formatted
    assert "Assunto: Report" in formatted
    assert "Recebido em: 2026-11-02T10:00:00+00:00" in formatted
    assert formatted.endswith("Hello")


def test_format_email_uses_email_when_no_name():
    from dataclasses import replace

    anonymous = replace(_email(), sender_name="")

    assert format_reply("netflix", anonymous).startswith("Último email de 'netflix'")


def test_format_email_empty_body():
    assert format_reply("netflix", _email(body="")).endswith("(sem conteúdo de texto)")


def test_short_text_is_not_split():
    assert split_text("short", 100) == ["short"]


def test_long_text_is_split_by_lines():
    text = "\n".join(f"line {i} " + "x" * 30 for i in range(200))

    chunks = split_text(text, max_length=1000)

    assert all(len(chunk) <= 1000 for chunk in chunks)
    assert all(chunk for chunk in chunks)


def test_chunks_reconstruct_original_content():
    text = "word " * 3000

    joined = "---".join(split_text(text, max_length=1000))

    assert len(joined) > len(text)


def test_very_long_single_line_is_split_hard():
    chunks = split_text("a" * 5000, max_length=4096)

    assert len(chunks) == 2
    assert all(len(chunk) <= 4096 for chunk in chunks)
