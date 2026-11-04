from __future__ import annotations

import argparse
import logging
import sys

from googleapiclient.discovery import build

from .config import ConfigError, load_config
from .gmail.client import GmailClient, authenticate
from .services.code_requests import CodeRequestService
from .telegram.bot import TelegramBot
from .telegram.client import TelegramClient

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Telegram bot that fetches the latest email from configured senders"
    )
    parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    if not config.allowed_chat_ids:
        logger.warning(
            "ALLOWED_CHAT_IDS is empty: everyone can use the bot. "
            "Send a message to the bot and copy the logged chat id into .env."
        )

    try:
        credentials = authenticate(
            config.google_credentials_path, config.google_token_path
        )
    except Exception as exc:
        logger.error("Gmail authentication failed: %s", exc)
        sys.exit(1)

    gmail_client = GmailClient(
        build("gmail", "v1", credentials=credentials, cache_discovery=False)
    )
    telegram_client = TelegramClient(config.telegram_bot_token)
    code_service = CodeRequestService(gmail_client, config.service_senders)
    bot = TelegramBot(telegram_client, code_service, config.allowed_chat_ids)

    try:
        bot.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")


if __name__ == "__main__":
    main()
