from __future__ import annotations

import logging
import re
import time

from ..gmail.parser import EmailMessage
from ..telegram.client import TelegramClient
from ..services.code_requests import CodeRequestService, UnknownServiceError

logger = logging.getLogger(__name__)

_LONG_POLL_TIMEOUT = 25
_ERROR_BACKOFF_SECONDS = 5


class TelegramBot:
    def __init__(
        self,
        telegram_client: TelegramClient,
        code_service: CodeRequestService,
        allowed_chat_ids: frozenset[int] = frozenset(),
    ) -> None:
        self._telegram = telegram_client
        self._code_service = code_service
        self._allowed_chat_ids = allowed_chat_ids

    def run_forever(self) -> None:
        logger.info(
            "Starting Telegram bot; services: %s",
            ", ".join(self._code_service.aliases()),
        )
        offset = 0
        while True:
            try:
                updates = self._telegram.get_updates(
                    offset, timeout=_LONG_POLL_TIMEOUT
                )
            except Exception:
                logger.exception("Failed to fetch Telegram updates")
                time.sleep(_ERROR_BACKOFF_SECONDS)
                continue

            for update in updates:
                offset = max(offset, update.get("update_id", offset - 1)) + 1
                try:
                    self.handle_update(update)
                except Exception:
                    logger.exception("Failed to handle Telegram update %s", update)

    def handle_update(self, update: dict) -> None:
        message = update.get("message")
        if not message:
            return
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = message.get("text", "").strip()
        if chat_id is None or not text:
            return

        if self._allowed_chat_ids and chat_id not in self._allowed_chat_ids:
            logger.warning("Rejected request from unauthorized chat %s", chat_id)
            self._reply(chat_id, "Você não está autorizado a usar este bot.")
            return

        if text.startswith(("/start", "/help")):
            self._reply(chat_id, self._usage())
            return

        self._reply(chat_id, self._response_for(text))

    def _response_for(self, text: str) -> str:
        alias = text.lstrip("/").removeprefix("code ").strip()
        try:
            message = self._code_service.find_latest(alias)
        except UnknownServiceError as exc:
            return self._unknown_service_text(exc.available)
        except Exception:
            logger.exception("Failed to fetch latest code for %r", alias)
            return "Ocorreu um erro ao buscar o email. Tente novamente mais tarde."

        if message is None:
            return f"Nenhum email recente encontrado para '{alias}'."
        return self._code_response(alias, message)

    def _code_response(self, alias: str, message: EmailMessage) -> str:
        match = re.search(self._code_service.code_pattern(alias), message.body)
        if match is None:
            return format_reply(alias, message)
        code = match.group(1) if match.groups() else match.group(0)
        sender_name = message.sender_name.strip()
        sender = (
            f"{sender_name} <{message.sender_email}>"
            if sender_name
            else message.sender_email
        )
        return (
            f"Código para '{alias}': {code}\n"
            f"De: {sender}\n"
            f"Assunto: {message.subject}\n"
            f"Recebido em: {message.received_at}"
        )

    def _unknown_service_text(
        self, available: list[str] | None = None
    ) -> str:
        services = available if available is not None else self._code_service.aliases()

        services_text = "\n".join(f"  • {service}" for service in services)

        return (
            "Serviço não configurado.\n\n"
            "Os seguintes serviços estão disponíveis:\n"
            f"{services_text}\n\n"
        )

    def _usage(self) -> str:
        services = ", ".join(self._code_service.aliases()) or "(nenhum configurado)"
        return (
            "Envie o nome de um serviço para receber o código do email mais "
            f"recente.\nServiços disponíveis: {services}"
        )

    def _reply(self, chat_id: int, text: str) -> None:
        try:
            self._telegram.deliver(chat_id, text)
        except Exception:
            logger.exception("Failed to send reply to chat %s", chat_id)


def format_reply(alias: str, message: EmailMessage) -> str:
    sender = message.sender_name or message.sender_email
    header = (
        f"Último email de '{alias}'\n"
        f"De: {sender} <{message.sender_email}>\n"
        f"Assunto: {message.subject}\n"
        f"Recebido em: {message.received_at}"
    )
    body = message.body or "(sem conteúdo de texto)"
    return f"{header}\n\n{body}"
