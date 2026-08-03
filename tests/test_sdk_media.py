from __future__ import annotations

from meta_cli.config import MetaCredentials
from meta_cli.sdk import MetaSDKClient


class FakeVideoResult:
    def export_all_data(self):
        return {"id": "video_123"}


class FakeAccount:
    def __init__(self):
        self.params = None

    def create_ad_video(self, params):
        self.params = params
        return FakeVideoResult()


def test_upload_video_uses_official_sdk_source_file_parameter(tmp_path, monkeypatch):
    video = tmp_path / "creative.mp4"
    video.write_bytes(b"video")
    client = MetaSDKClient(
        MetaCredentials.model_validate(
            {
                "META_ACCESS_TOKEN": "token",
                "META_APP_ID": "app",
                "META_APP_SECRET": "secret",
                "META_AD_ACCOUNT_ID": "123",
            }
        )
    )
    account = FakeAccount()
    monkeypatch.setattr(client, "initialize", lambda: None)
    monkeypatch.setattr(client, "get_ad_account", lambda: account)

    result = client.upload_video(str(video))

    assert account.params == {"source": str(video)}
    assert result == {"id": "video_123"}
