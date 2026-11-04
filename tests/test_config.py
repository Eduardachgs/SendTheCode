from __future__ import annotations

import pytest

from email_telegram_bot.config import ConfigError, load_config


VALID_ENV = {
    "TELEGRAM_BOT_TOKEN": "token123",
    "SERVICE_SENDERS": "netflix=Infos@Netflix.Com, disney=no-reply@mailer.disney.com",
    "ALLOWED_CHAT_IDS": "42, 7 ",
}


def test_load_config_parses_services_and_chat_ids():
    config = load_config(env=dict(VALID_ENV))

    assert config.telegram_bot_token == "token123"
    assert config.service_senders["netflix"] == "infos@netflix.com"
    assert config.service_senders["disney"] == "no-reply@mailer.disney.com"
    assert config.allowed_chat_ids == frozenset({42, 7})


def test_existing_env_vars_take_precedence():
    config = load_config(
        env={
            "TELEGRAM_BOT_TOKEN": "t",
            "SERVICE_SENDERS": "netflix=info@message.netflix.com",
        }
    )

    assert config.allowed_chat_ids == frozenset()
    assert config.google_credentials_path.name == "credentials.json"
    assert config.google_token_path.name == "token.json"


def test_missing_required_variable_raises():
    without_token = {k: v for k, v in VALID_ENV.items() if k != "TELEGRAM_BOT_TOKEN"}

    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        load_config(env=without_token)


def test_empty_allowed_chat_ids_is_allowed():
    env = {k: v for k, v in VALID_ENV.items() if k != "ALLOWED_CHAT_IDS"}

    assert load_config(env=env).allowed_chat_ids == frozenset()


@pytest.mark.parametrize(
    ("raw_services", "error_fragment"),
    [
        ("netflix", "'alias=sender'"),
        ("netflix=", "empty"),
        ("=info@netflix.com", "empty"),
        ("netflix=a@x.com,netflix=b@x.com", "duplicated alias"),
    ],
)
def test_invalid_service_senders_raise(raw_services, error_fragment):
    env = dict(VALID_ENV) | {"SERVICE_SENDERS": raw_services}

    with pytest.raises(ConfigError) as exc_info:
        load_config(env=env)

    assert error_fragment in str(exc_info.value)


def test_trailing_commas_are_ignored():
    env = dict(VALID_ENV) | {"SERVICE_SENDERS": "netflix=info@netflix.com, ,"}

    assert load_config(env=env).service_senders["netflix"] == "info@netflix.com"


def test_invalid_allowed_chat_ids_raise():
    env = dict(VALID_ENV) | {"ALLOWED_CHAT_IDS": "42,not-numeric"}

    with pytest.raises(ConfigError, match="ALLOWED_CHAT_IDS"):
        load_config(env=env)
