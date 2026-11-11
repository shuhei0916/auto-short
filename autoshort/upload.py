"""YouTube upload via Data API v3.

Needs secrets/client_secret.json (OAuth client, type "Desktop app").
The first run opens a browser for consent and caches secrets/token.json.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

# Read-only scopes are requested up front so the analytics loop needs no second consent.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
SECRETS = Path("secrets")


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token = SECRETS / "token.json"
    client = SECRETS / "client_secret.json"
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not client.exists():
                raise SystemExit(f"Missing {client}. See README (YouTube setup).")
            creds = InstalledAppFlow.from_client_secrets_file(str(client), SCOPES).run_local_server(port=0)
        token.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def upload(video: Path, privacy: str = "private", publish_at: str | None = None) -> str:
    from googleapiclient.http import MediaFileUpload

    meta_path = video.with_suffix(".json")
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
