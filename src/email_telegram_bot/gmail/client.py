from __future__ import annotations

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

_CANDIDATE_RESULTS_TO_FETCH = 5


class GmailError(Exception):
    pass


def authenticate(credentials_path: Path, token_path: Path) -> Credentials:
    credentials = _load_saved_credentials(token_path)
    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        logger.info("Refreshing Gmail OAuth token")
        credentials.refresh(Request())
    else:
        credentials = _run_oauth_flow(credentials_path)

    _save_credentials(credentials, token_path)
    return credentials


def _load_saved_credentials(token_path: Path) -> Credentials | None:
    if not token_path.exists():
        return None
    return Credentials.from_authorized_user_file(str(token_path), SCOPES)


def _run_oauth_flow(credentials_path: Path) -> Credentials:
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"OAuth credentials file not found: {credentials_path}. "
            "Download it from Google Cloud Console and set GOOGLE_CREDENTIALS_PATH."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    logger.info("Starting OAuth flow, a browser window will open")
    return flow.run_local_server(port=0)


def _save_credentials(credentials: Credentials, token_path: Path) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json())


class GmailClient:
    def __init__(self, service) -> None:
        self._service = service

    def find_latest_message(self, sender: str) -> dict | None:
        messages = self._search(f"from:{sender}")
        if not messages:
            return None

        latest: dict | None = None
        latest_timestamp = -1
        for candidate in messages[:_CANDIDATE_RESULTS_TO_FETCH]:
            message = self._get(candidate["id"])
            timestamp = int(message.get("internalDate") or 0)
            if timestamp > latest_timestamp:
                latest, latest_timestamp = message, timestamp
        return latest

    def _search(self, query: str) -> list[dict]:
        try:
            response = (
                self._service.users()
                .messages()
                .list(userId="me", q=query, maxResults=_CANDIDATE_RESULTS_TO_FETCH)
                .execute()
            )
        except HttpError as exc:
            raise GmailError(f"Gmail search failed for query {query!r}: {exc}") from exc
        return list(response.get("messages", []))

    def _get(self, gmail_id: str) -> dict:
        try:
            return (
                self._service.users()
                .messages()
                .get(userId="me", id=gmail_id, format="full")
                .execute()
            )
        except HttpError as exc:
            raise GmailError(f"Gmail get failed for message {gmail_id!r}: {exc}") from exc
