from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    allowed_chat_ids: frozenset[int]
    service_senders: Mapping[str, str]
    google_credentials_path: Path
    google_token_path: Path


def _required(env: dict[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def _service_senders(env: dict[str, str]) -> dict[str, str]:
    raw = _required(env, "SERVICE_SENDERS")
    senders: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise ConfigError(
                f"SERVICE_SENDERS entries must be 'alias=sender', got: {pair!r}"
            )
        alias, sender = pair.split("=", 1)
        alias, sender = alias.strip().lower(), sender.strip().lower()
        if not alias or not sender:
            raise ConfigError(
                f"SERVICE_SENDERS alias and sender must not be empty: {pair!r}"
            )
        if alias in senders:
            raise ConfigError(f"SERVICE_SENDERS has duplicated alias: {alias!r}")
        senders[alias] = sender
    if not senders:
        raise ConfigError("SERVICE_SENDERS must define at least one service")
    return senders


def _allowed_chat_ids(env: dict[str, str]) -> frozenset[int]:
    raw = env.get("ALLOWED_CHAT_IDS", "").strip()
    if not raw:
        return frozenset()
    ids: set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.add(int(chunk))
        except ValueError as exc:
            raise ConfigError(f"ALLOWED_CHAT_IDS must be integers: {chunk!r}") from exc
    return frozenset(ids)


def load_config(env: dict[str, str] | None = None, env_file: str | None = None) -> Config:
    if env is None:
        load_dotenv(env_file)
        env = dict(os.environ)

    service_senders = _service_senders(env)
    return Config(
        telegram_bot_token=_required(env, "TELEGRAM_BOT_TOKEN"),
        allowed_chat_ids=_allowed_chat_ids(env),
        service_senders=service_senders,
        google_credentials_path=Path(
            env.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        ),
        google_token_path=Path(env.get("GOOGLE_TOKEN_PATH", "token.json")),
    )
