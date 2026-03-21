from __future__ import annotations

from typer.testing import CliRunner

from meta_cli.app import app

runner = CliRunner()


def test_auth_test_success(monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN", "token")
    monkeypatch.setenv("META_APP_ID", "app")
    monkeypatch.setenv("META_APP_SECRET", "secret")
    monkeypatch.setenv("META_AD_ACCOUNT_ID", "123")

    class FakeClient:
        def __init__(self, _):
            pass

        def test_auth(self):
            return {"id": "act_123", "name": "Test Account", "account_status": 1}

    monkeypatch.setattr("meta_cli.commands.auth.MetaSDKClient", FakeClient)

    result = runner.invoke(app, ["auth", "test"])

    assert result.exit_code == 0
    assert "Authentication successful" in result.stdout


def test_auth_test_failure(monkeypatch):
    result = runner.invoke(app, ["auth", "test", "--json"])

    assert result.exit_code == 1
    assert '"ok": false' in result.stdout.lower()
