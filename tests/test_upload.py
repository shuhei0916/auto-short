import json
from pathlib import Path

from autoshort.schedule import HISTORY_DIR, meta_path_for
from autoshort.upload import _load_credentials

FAKE_TOKEN = {
    "token": "access",
    "refresh_token": "refresh-123",
    "client_id": "cid.apps.googleusercontent.com",
    "client_secret": "csecret",
    "token_uri": "https://oauth2.googleapis.com/token",
}


def test_metadata_is_kept_in_the_tracked_history_dir():
    assert HISTORY_DIR == Path("history")
    assert meta_path_for(Path("out/ball_grow_00005.mp4")) == Path("history/ball_grow_00005.json")


def test_credentials_come_from_env_in_ci(monkeypatch, tmp_path):
    monkeypatch.setenv("YT_TOKEN_JSON", json.dumps(FAKE_TOKEN))
    monkeypatch.chdir(tmp_path)  # no secrets/ dir here
    creds, token_file = _load_credentials()
    assert creds.refresh_token == "refresh-123"
    assert token_file is None  # never write the CI token to disk


def test_without_env_the_local_token_file_is_used(monkeypatch, tmp_path):
    monkeypatch.delenv("YT_TOKEN_JSON", raising=False)
    monkeypatch.chdir(tmp_path)
    creds, token_file = _load_credentials()
    assert creds is None
    assert token_file == Path("secrets/token.json")
