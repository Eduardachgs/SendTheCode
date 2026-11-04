from __future__ import annotations

import base64
from unittest.mock import MagicMock

import pytest

from email_telegram_bot.gmail.parser import EmailMessage
from email_telegram_bot.services.code_requests import CodeRequestService
from email_telegram_bot.telegram.bot import TelegramBot, format_reply


HELLO_DATA = base64.urlsafe_b64encode(b"Codigo 123456").decode()


def _gmail_message(sender="info@message.netflix.com"):
    return {
        "id": "m1",
        "internalDate": "1762200000000",
        "payload": {
            "headers": [
                {"name": "From", "value": f"Netflix <{sender}>"},
                {"name": "To", "value": " jogador@gmail.com"},
                {"name": "Subject", "value": "Your code"},
            ],
            "parts": [{"mimeType": "text/plain", "body": {"data": HELLO_DATA}}],
        },
    }


def _parsed_message(sender="info@message.netflix.com", body="Codigo 123456"):
    return EmailMessage(
        gmail_id="m1",
        sender_name="Netflix",
        sender_email=sender,
        recipients="jogador@gmail.com",
        subject="Your code",
        received_at="2026-11-03T09:20:00+00:00",
        body=body,
    )


def _bot(monkeypatch,
         gmail_message=None,
         service_senders={"netflix": "info@message.netflix.com"},
         allowed_chat_ids=frozenset({42})):
    from email_telegram_bot.services import code_requests as module

    if gmail_message is not None:
        monkeypatch.setattr(
            module, "parse_message", lambda gmail_id, message: gmail_message
        )

    telegram = MagicMock()
    gmail = MagicMock()
    gmail.find_latest_message.return_value = {"id": "m1"}
    code_service = CodeRequestService(gmail, service_senders)
    bot = TelegramBot(telegram, code_service, allowed_chat_ids)
    return bot, telegram, code_service, gmail


def test_help_lists_available_services(monkeypatch):
    bot, telegram, _, _ = _bot(monkeypatch)

    bot.handle_update({"message": {"chat": {"id": 42}, "text": "/help"}})

    text = telegram.deliver.call_args[0][1]
    assert "netflix" in text


def test_alias_request_replies_with_latest_email(monkeypatch):
    expected = _parsed_message()
    monkeypatch.setattr(
        "email_telegram_bot.services.code_requests.parse_message",
        lambda gmail_id, message: expected,
    )
    bot, telegram, code_service, gmail = _bot(monkeypatch)

    bot.handle_update({"message": {"chat": {"id": 42}, "text": "Netflix"}})

    gmail.find_latest_message.assert_called_once_with("info@message.netflix.com")
    telegram.deliver.assert_called_once()
    args = telegram.deliver.call_args[0]
    assert args[0] == 42
    assert args[1].startswith("Código para 'Netflix': 123456")


def test_no_recent_email_replies_friendly_message(monkeypatch):
    bot, telegram, _, gmail = _bot(monkeypatch)
    gmail.find_latest_message.return_value = None

    bot.handle_update({"message": {"chat": {"id": 42}, "text": "netflix"}})

    text = telegram.deliver.call_args[0][1]
    assert "Nenhum email recente" in text


def test_unknown_service_replies_with_available_list(monkeypatch):
    bot, telegram, _, _ = _bot(
        monkeypatch, service_senders={"netflix": "a@x.com", "disney": "b@x.com"}
    )

    bot.handle_update({"message": {"chat": {"id": 42}, "text": "hulu"}})

    text = telegram.deliver.call_args[0][1]
    assert "Serviço não configurado" in text
    assert "netflix" in text and "disney" in text


def test_unauthorized_user_is_rejected(monkeypatch):
    bot, telegram, _, gmail = _bot(monkeypatch)

    bot.handle_update({"message": {"chat": {"id": 999}, "text": "netflix"}})

    text = telegram.deliver.call_args[0][1]
    assert "não está autorizado" in text
    gmail.find_latest_message.assert_not_called()


def test_open_bot_allows_everyone(monkeypatch):
    bot, telegram, _, _ = _bot(monkeypatch, allowed_chat_ids=frozenset())

    bot.handle_update({"message": {"chat": {"id": 999}, "text": "/help"}})

    text = telegram.deliver.call_args[0][1]
    assert "Serviços disponíveis" in text


def test_server_failure_replies_transient_message(monkeypatch):
    bot, telegram, _, gmail = _bot(monkeypatch)
    gmail.find_latest_message.side_effect = RuntimeError("gmail down")

    bot.handle_update({"message": {"chat": {"id": 42}, "text": "netflix"}})

    text = telegram.deliver.call_args[0][1]
    assert "Ocorreu um erro" in text


def test_delivery_failure_does_not_crash_handler(monkeypatch):
    bot, telegram, _, _ = _bot(
        monkeypatch, allowed_chat_ids=frozenset()
    )
    telegram.deliver.side_effect = Exception("telegram down")

    bot.handle_update({"message": {"chat": {"id": 42}, "text": "/help"}})


def test_updates_without_text_or_chat_are_ignored(monkeypatch):
    bot, telegram, _, _ = _bot(monkeypatch)

    bot.handle_update({"message": {"chat": {"id": 42}}})
    bot.handle_update({})

    telegram.deliver.assert_not_called()


def test_non_message_update_is_ignored(monkeypatch):
    bot, telegram, _, _ = _bot(monkeypatch)

    bot.handle_update({"callback_query": {"data": "netflix"}})

    telegram.deliver.assert_not_called()


def test_format_reply_contains_alias_metadata_and_code():
    text = format_reply("netflix", _parsed_message())

    assert text.startswith("Último email de 'netflix'")
    assert "info@message.netflix.com" in text
    assert "Your code" in text
    assert text.endswith("Codigo 123456")


def test_format_reply_handles_empty_body():
    assert format_reply("netflix", _parsed_message(body="")).endswith(
        "(sem conteúdo de texto)"
    )


def _code_message(body="Seu código único\n------\n\n358445"):
    return _parsed_message(sender="no-reply@alerts.hbomax.com", body=body)


def test_response_with_code_match_replies_code_first(monkeypatch):
    code_email = _code_message()

    def fake_parse(gmail_id, message):
        return code_email

    bot, telegram, code_service, gmail = _bot(
        monkeypatch,
        service_senders={"hbo": "no-reply@alerts.hbomax.com"},
    )
    monkeypatch.setattr(
        "email_telegram_bot.services.code_requests.parse_message", fake_parse
    )

    bot.handle_update({"message": {"chat": {"id": 42}, "text": "hbo"}})

    text = telegram.deliver.call_args[0][1]
    assert text.startswith("Código para 'hbo': 358445")
    assert "De: Netflix <no-reply@alerts.hbomax.com>" in text


def test_response_without_code_match_falls_back_to_full_email(monkeypatch):
    bot, telegram, _, _ = _bot(
        monkeypatch,
        service_senders={"hbo": "no-reply@alerts.hbomax.com"},
    )
    monkeypatch.setattr(
        "email_telegram_bot.services.code_requests.parse_message",
        lambda gmail_id, message: _code_message(body="sem numero nenhum aqui"),
    )

    bot.handle_update({"message": {"chat": {"id": 42}, "text": "hbo"}})

    text = telegram.deliver.call_args[0][1]
    assert text.startswith("Último email de 'hbo'")
    assert "sem numero nenhum aqui" in text
