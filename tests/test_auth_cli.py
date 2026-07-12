from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from meta_cli.app import app
from meta_cli.exceptions import APIError

runner = CliRunner()

PROFILE_TOKEN = "selected-token-never-print"
PROFILE_SECRET = "selected-secret-never-print"


@pytest.fixture(autouse=True)
def isolate_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(tmp_path / "environments.yaml"))
    for key in (
        "META_ACCESS_TOKEN",
        "META_APP_ID",
        "META_APP_SECRET",
        "META_AD_ACCOUNT_ID",
        "META_API_VERSION",
    ):
        monkeypatch.delenv(key, raising=False)


def _write_selected_profile(path):
    path.write_text(
        f"""
active_profile: sandbox
profiles:
  sandbox:
    access_token: {PROFILE_TOKEN}
    app_id: selected-app
    app_secret: {PROFILE_SECRET}
    ad_account_id: 123
    api_version: v23.0
""".strip()
    )


def test_auth_test_uses_selected_environment(tmp_path, monkeypatch):
    path = tmp_path / "environments.yaml"
    _write_selected_profile(path)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(path))
    captured = {}

    class FakeClient:
        def __init__(self, credentials):
            captured["credentials"] = credentials

        def test_auth(self):
            return {"id": "act_123", "name": "Test Account", "account_status": 1}

    monkeypatch.setattr("meta_cli.commands.auth.MetaSDKClient", FakeClient)

    result = runner.invoke(app, ["auth", "test"])

    assert result.exit_code == 0
    assert captured["credentials"].access_token == PROFILE_TOKEN
    assert captured["credentials"].app_secret == PROFILE_SECRET
    assert captured["credentials"].api_version == "v23.0"
    assert "Authentication successful" in result.stdout
    assert "Active environment: sandbox" in result.stdout
    assert PROFILE_TOKEN not in result.stdout
    assert PROFILE_SECRET not in result.stdout


def test_auth_test_json_reports_selected_environment(tmp_path, monkeypatch):
    path = tmp_path / "environments.yaml"
    _write_selected_profile(path)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(path))

    class FakeClient:
        def __init__(self, _credentials):
            pass

        def test_auth(self):
            return {"id": "act_123", "name": "Test Account", "account_status": 1}

    monkeypatch.setattr("meta_cli.commands.auth.MetaSDKClient", FakeClient)

    result = runner.invoke(app, ["auth", "test", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["auth_source"] == "named_environment"
    assert payload["active_environment"] == "sandbox"
    assert PROFILE_TOKEN not in result.stdout
    assert PROFILE_SECRET not in result.stdout


def test_explicit_legacy_auth_file_overrides_selected_environment(tmp_path, monkeypatch):
    environments = tmp_path / "environments.yaml"
    _write_selected_profile(environments)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(environments))
    legacy = tmp_path / "legacy.yaml"
    legacy.write_text(
        """
META_ACCESS_TOKEN: legacy-file-token
META_APP_ID: legacy-file-app
META_APP_SECRET: legacy-file-secret
META_AD_ACCOUNT_ID: 999
META_API_VERSION: v22.0
""".strip()
    )
    monkeypatch.setenv("META_ACCESS_TOKEN", "legacy-env-token")
    captured = {}

    class FakeClient:
        def __init__(self, credentials):
            captured["credentials"] = credentials

        def test_auth(self):
            return {"id": "act_999", "name": "Legacy", "account_status": 1}

    monkeypatch.setattr("meta_cli.commands.auth.MetaSDKClient", FakeClient)

    result = runner.invoke(app, ["auth", "test", "--config", str(legacy)])

    assert result.exit_code == 0
    assert captured["credentials"].access_token == "legacy-env-token"
    assert captured["credentials"].app_id == "legacy-file-app"
    assert captured["credentials"].ad_account_id == "act_999"
    assert captured["credentials"].access_token != PROFILE_TOKEN
    assert "Active environment: none (explicit legacy config override)" in result.stdout
    assert "Active environment: sandbox" not in result.stdout
    for secret in (
        PROFILE_TOKEN,
        PROFILE_SECRET,
        "legacy-file-token",
        "legacy-file-secret",
        "legacy-env-token",
    ):
        assert secret not in result.stdout


def test_auth_test_json_distinguishes_legacy_override(tmp_path, monkeypatch):
    environments = tmp_path / "environments.yaml"
    _write_selected_profile(environments)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(environments))
    legacy = tmp_path / "legacy.yaml"
    legacy.write_text(
        """
META_ACCESS_TOKEN: legacy-json-token
META_APP_ID: legacy-json-app
META_APP_SECRET: legacy-json-secret
META_AD_ACCOUNT_ID: 999
""".strip()
    )

    class FakeClient:
        def __init__(self, _credentials):
            pass

        def test_auth(self):
            return {"id": "act_999", "name": "Legacy", "account_status": 1}

    monkeypatch.setattr("meta_cli.commands.auth.MetaSDKClient", FakeClient)

    result = runner.invoke(app, ["auth", "test", "--config", str(legacy), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["auth_source"] == "legacy_config"
    assert payload["active_environment"] is None
    assert "sandbox" not in result.stdout
    assert "legacy-json-token" not in result.stdout
    assert "legacy-json-secret" not in result.stdout


def test_standard_command_selected_profile_and_legacy_override(tmp_path, monkeypatch):
    environments = tmp_path / "environments.yaml"
    _write_selected_profile(environments)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(environments))
    legacy = tmp_path / "legacy.yaml"
    legacy.write_text(
        """
META_ACCESS_TOKEN: standard-legacy-token
META_APP_ID: standard-legacy-app
META_APP_SECRET: standard-legacy-secret
META_AD_ACCOUNT_ID: 999
""".strip()
    )
    captured = []

    class FakeClient:
        def __init__(self, credentials):
            captured.append(credentials)

        def list_campaigns(self, **_kwargs):
            return []

    monkeypatch.setattr("meta_cli.cli_utils.MetaSDKClient", FakeClient)

    selected = runner.invoke(app, ["campaigns", "list", "--json"])
    overridden = runner.invoke(
        app,
        ["campaigns", "list", "--auth-config", str(legacy), "--json"],
    )

    assert selected.exit_code == 0
    assert overridden.exit_code == 0
    assert captured[0].access_token == PROFILE_TOKEN
    assert captured[0].ad_account_id == "act_123"
    assert captured[1].access_token == "standard-legacy-token"
    assert captured[1].ad_account_id == "act_999"
    combined_output = selected.stdout + overridden.stdout
    assert PROFILE_TOKEN not in combined_output
    assert PROFILE_SECRET not in combined_output
    assert "standard-legacy-token" not in combined_output
    assert "standard-legacy-secret" not in combined_output


def test_auth_test_without_selection_has_actionable_safe_failure(tmp_path):
    path = tmp_path / "environments.yaml"
    path.write_text("active_profile: null\nprofiles: {}\n")

    result = runner.invoke(
        app,
        ["auth", "test", "--json"],
        env={"META_CLI_ENVIRONMENTS_FILE": str(path)},
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert "No active Meta Ads environment" in payload["error"]
    assert "environments use <name>" in payload["error"]


def test_auth_test_stale_selection_has_actionable_safe_failure(tmp_path):
    path = tmp_path / "environments.yaml"
    path.write_text(
        f"""
active_profile: removed
profiles:
  available:
    access_token: {PROFILE_TOKEN}
    app_id: available-app
    app_secret: {PROFILE_SECRET}
    ad_account_id: 123
""".strip()
    )

    result = runner.invoke(
        app,
        ["auth", "test", "--json"],
        env={"META_CLI_ENVIRONMENTS_FILE": str(path)},
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert "'removed' no longer exists" in payload["error"]
    assert "environments use <name>" in payload["error"]
    assert PROFILE_TOKEN not in result.stdout
    assert PROFILE_SECRET not in result.stdout


def test_malformed_legacy_auth_file_does_not_echo_secret(tmp_path):
    legacy = tmp_path / "legacy.yaml"
    malformed_secret = "malformed-secret-never-print"
    legacy.write_text(f"META_ACCESS_TOKEN: [{malformed_secret}\n")

    result = runner.invoke(app, ["auth", "test", "--config", str(legacy), "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["auth_source"] == "legacy_config"
    assert payload["active_environment"] is None
    assert "Invalid YAML in config file" in payload["error"]
    assert malformed_secret not in result.stdout


@pytest.mark.parametrize("json_output", [False, True])
def test_authentication_api_error_redacts_selected_secrets(
    tmp_path, monkeypatch, json_output
):
    path = tmp_path / "environments.yaml"
    _write_selected_profile(path)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(path))

    class FakeClient:
        def __init__(self, _credentials):
            pass

        def test_auth(self):
            raise APIError(f"request included {PROFILE_TOKEN} and {PROFILE_SECRET}")

    monkeypatch.setattr("meta_cli.commands.auth.MetaSDKClient", FakeClient)

    arguments = ["auth", "test"]
    if json_output:
        arguments.append("--json")
    result = runner.invoke(app, arguments)

    assert result.exit_code == 1
    assert "[REDACTED]" in result.stdout
    assert PROFILE_TOKEN not in result.stdout
    assert PROFILE_SECRET not in result.stdout
