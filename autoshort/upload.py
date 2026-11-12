"""YouTube upload via Data API v3.

Locally: needs secrets/client_secret.json (OAuth client, type "Desktop app");
the first run opens a browser for consent and caches secrets/token.json.
In CI: set YT_TOKEN_JSON to the contents of that token.json.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

# Read-only scopes are requested up front so the analytics loop needs no second consent.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
SECRETS = Path("secrets")


def _load_credentials():
    """Returns (credentials or None, token file to cache refreshed tokens in, or None)."""
    from google.oauth2.credentials import Credentials

    env = os.environ.get("YT_TOKEN_JSON")
    if env:
        return Credentials.from_authorized_user_info(json.loads(env), SCOPES), None
    token = SECRETS / "token.json"
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    return creds, token


def _service():
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds, token = _load_credentials()
    client = SECRETS / "client_secret.json"
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif token is None:
            raise SystemExit("YT_TOKEN_JSON holds no usable refresh token.")
        else:
            if not client.exists():
                raise SystemExit(f"Missing {client}. See README (YouTube setup).")
            creds = InstalledAppFlow.from_client_secrets_file(str(client), SCOPES).run_local_server(port=0)
        if token is not None:
            token.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def upload(video: Path, privacy: str = "private", publish_at: str | None = None) -> str:
    from googleapiclient.http import MediaFileUpload

    from .schedule import meta_path_for

    meta_path = meta_path_for(video)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("uploaded"):
        raise SystemExit(f"Already uploaded: {meta['uploaded']['url']}")

    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at
    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": "24",  # Entertainment
        },
        "status": status,
    }
    req = _service().videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True),
    )
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    url = f"https://youtube.com/shorts/{resp['id']}"
    meta["uploaded"] = {
        "id": resp["id"],
        "url": url,
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "privacy": status["privacyStatus"],
        "publish_at": publish_at,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(url)
    return url
