from __future__ import annotations

import pytest

from meta_cli.config import MetaCredentials
from meta_cli.exceptions import APIError
from meta_cli.sdk import MetaSDKClient


def _creds() -> MetaCredentials:
    return MetaCredentials.model_validate(
        {
            "META_ACCESS_TOKEN": "token",
            "META_APP_ID": "app",
            "META_APP_SECRET": "secret",
            "META_AD_ACCOUNT_ID": "act_123",
        }
    )


def test_parse_video_processing_status_ready():
    payload = {"status": {"video_status": "ready", "processing_progress": 100}}
    parsed = MetaSDKClient.parse_video_processing_status(payload)
    assert parsed["is_complete"] is True
    assert parsed["is_failed"] is False
    assert parsed["progress"] == 100


def test_wait_for_video_processing_completes(monkeypatch):
    client = MetaSDKClient(_creds())
    statuses = iter(
        [
            {"status": {"video_status": "processing", "processing_progress": 20}},
            {"status": {"video_status": "processing", "processing_progress": 80}},
            {"status": {"video_status": "ready", "processing_progress": 100}},
        ]
    )
    monkeypatch.setattr(client, "get_video_status", lambda _video_id: next(statuses))
    monkeypatch.setattr("meta_cli.sdk.time.sleep", lambda _n: None)

    updates = []
    result = client.wait_for_video_processing("video1", poll_interval=0.1, timeout=5, on_update=updates.append)

    assert result["is_complete"] is True
    assert updates[-1]["progress"] == 100


def test_wait_for_video_processing_timeout(monkeypatch):
    client = MetaSDKClient(_creds())
    monkeypatch.setattr(
        client,
        "get_video_status",
        lambda _video_id: {"status": {"video_status": "processing", "processing_progress": 10}},
    )
    monkeypatch.setattr("meta_cli.sdk.time.sleep", lambda _n: None)

    ticks = iter([0.0, 0.4, 0.9, 1.5])
    monkeypatch.setattr("meta_cli.sdk.time.monotonic", lambda: next(ticks))

    with pytest.raises(APIError):
        client.wait_for_video_processing("video1", poll_interval=0.1, timeout=1)
