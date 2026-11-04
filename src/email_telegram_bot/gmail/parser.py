from __future__ import annotations

import base64
import email.header
import email.utils
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class EmailMessage:
    gmail_id: str
    sender_name: str
    sender_email: str
    recipients: str
    subject: str
    received_at: str
    body: str


def parse_message(gmail_id: str, message: dict) -> EmailMessage:
    payload = message.get("payload", {})
    headers = {
        entry["name"].lower(): entry["value"]
        for entry in payload.get("headers", [])
        if "name" in entry and "value" in entry
    }

    sender_name, sender_email = email.utils.parseaddr(headers.get("from", ""))

    return EmailMessage(
        gmail_id=gmail_id,
        sender_name=sender_name,
        sender_email=sender_email.lower(),
        recipients=_join_recipients(headers),
        subject=_decode_normalized(headers.get("subject", "")),
        received_at=_received_at(message, headers.get("date", "")),
        body=_extract_body(payload),
    )


def _join_recipients(headers: dict[str, str]) -> str:
    recipients = [value.strip() for value in (headers.get("to", ""), headers.get("cc", "")) if value.strip()]
    return ", ".join(recipients)


def _decode_normalized(value: str) -> str:
    try:
        decoded = str(email.header.make_header(email.header.decode_header(value)))
    except Exception:
        decoded = value
    return re.sub(r"\s+", " ", decoded).strip()


def _received_at(payload: dict, date_header: str) -> str:
    internal_date = payload.get("internalDate")
    if internal_date:
        try:
            received = datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
            return received.isoformat()
        except (ValueError, OverflowError, OSError):
            pass
    return date_header


def _extract_body(payload: dict) -> str:
    plain = _find_part(payload, "text/plain")
    if plain is not None:
        return _decode_data(plain)
    html_part = _find_part(payload, "text/html")
    if html_part is not None:
        return _strip_html(_decode_data(html_part))
    return ""


def _find_part(payload: dict, mime_type: str) -> str | None:
    if payload.get("mimeType") == mime_type:
        data = payload.get("body", {}).get("data")
        if data and not payload.get("filename"):
            return data
    for part in payload.get("parts", []):
        found = _find_part(part, mime_type)
        if found is not None:
            return found
    return None


def _decode_data(data: str) -> str:
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    return raw.decode("utf-8", errors="replace")


_HTML_BLOCK_TAGS = re.compile(
    r"</?(p|div|br|tr|table|li|ul|ol|h[1-6]|blockquote|pre)[^>]*>", re.IGNORECASE
)
_HTML_STYLE_SCRIPT = re.compile(r"<(style|script)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_HTML_TAGS = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    text = _HTML_STYLE_SCRIPT.sub("", text)
    text = _HTML_BLOCK_TAGS.sub("\n", text)
    text = _HTML_TAGS.sub("", text)
    text = html.unescape(text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
