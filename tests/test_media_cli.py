from __future__ import annotations

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeMediaClient:
    def upload_image(self, path):
        return {"images": {"test": {"hash": "hash1", "path": path}}}

    def upload_video(self, path):
        return {"id": "video1", "path": path}


def test_upload_image(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.media.build_client", lambda *_: FakeMediaClient())
    result = runner.invoke(app, ["media", "upload-image", "image.jpg", "--json"])
    assert result.exit_code == 0
    assert '"hash": "hash1"' in result.stdout


def test_upload_video(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.media.build_client", lambda *_: FakeMediaClient())
    result = runner.invoke(app, ["media", "upload-video", "video.mp4", "--json"])
    assert result.exit_code == 0
    assert '"id": "video1"' in result.stdout
