from __future__ import annotations

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


class FakeMediaClient:
    def upload_image(self, path):
        return {"images": {"test": {"hash": "hash1", "path": path}}}

    def upload_video(self, path):
        return {"id": "video1", "path": path}

    def get_video_status(self, video_id):
        return {"id": video_id, "status": {"video_status": "ready"}}

    def parse_video_processing_status(self, status):
        return {
            "state": status["status"]["video_status"],
            "progress": None,
            "is_complete": True,
            "is_failed": False,
            "raw_status": status["status"],
        }

    def wait_for_video_processing(self, video_id, poll_interval, timeout, on_update=None):
        snapshot = {
            "video_id": video_id,
            "state": "ready",
            "progress": 100,
            "is_complete": True,
            "is_failed": False,
        }
        if on_update:
            on_update(snapshot)
        return snapshot


def test_upload_image(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.media.build_client", lambda *_: FakeMediaClient())
    result = runner.invoke(app, ["media", "upload-image", "image.jpg", "--json"])
    assert result.exit_code == 0
    assert '"hash": "hash1"' in result.stdout


def test_upload_video_waits_for_processing_by_default(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.media.build_client", lambda *_: FakeMediaClient())
    result = runner.invoke(app, ["media", "upload-video", "video.mp4", "--json"])
    assert result.exit_code == 0
    assert '"id": "video1"' in result.stdout
    assert '"processing"' in result.stdout
    assert '"is_complete": true' in result.stdout.lower()


def test_upload_video_no_wait(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.media.build_client", lambda *_: FakeMediaClient())
    result = runner.invoke(app, ["media", "upload-video", "video.mp4", "--no-wait", "--json"])
    assert result.exit_code == 0
    assert '"id": "video1"' in result.stdout
    assert '"processing"' not in result.stdout


def test_video_status_reads_existing_upload(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.media.build_client", lambda *_: FakeMediaClient())
    result = runner.invoke(app, ["media", "video-status", "video1", "--json"])
    assert result.exit_code == 0
    assert '"video_id": "video1"' in result.stdout
    assert '"state": "ready"' in result.stdout
    assert '"is_complete": true' in result.stdout.lower()


def test_video_status_can_wait_for_existing_upload(monkeypatch):
    monkeypatch.setattr("meta_cli.commands.media.build_client", lambda *_: FakeMediaClient())
    result = runner.invoke(app, ["media", "video-status", "video1", "--wait", "--json"])
    assert result.exit_code == 0
    assert '"video_id": "video1"' in result.stdout
    assert '"is_complete": true' in result.stdout.lower()
