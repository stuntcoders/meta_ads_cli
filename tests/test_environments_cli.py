from __future__ import annotations

import json

from typer.testing import CliRunner

from meta_cli.app import app
from meta_cli.config import load_settings

runner = CliRunner()

ENVIRONMENTS_YAML = """
active_profile: null
profiles:
  production:
    display_name: Production account
    access_token: production-token-never-print
    app_id: "101"
    app_secret: production-secret-never-print
    ad_account_id: "12345"
    api_version: v23.0
    system_user_id: "201"
    facebook_page_id: "301"
    instagram_user_id: "401"
  sandbox:
    display_name: Sandbox account
    access_token: sandbox-token-never-print
    app_id: "102"
    app_secret: sandbox-secret-never-print
    ad_account_id: "67890"
""".strip()

SECRETS = (
    "production-token-never-print",
    "production-secret-never-print",
    "sandbox-token-never-print",
    "sandbox-secret-never-print",
)


def test_environments_list_shows_only_safe_profile_identity(tmp_path):
    path = tmp_path / "environments.yaml"
    path.write_text(ENVIRONMENTS_YAML)

    result = runner.invoke(
        app,
        ["environments", "list", "--json"],
        env={"META_CLI_ENVIRONMENTS_FILE": str(path)},
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [item["name"] for item in payload] == ["production", "sandbox"]
    assert payload[0] == {
        "name": "production",
        "active": False,
        "display_name": "Production account",
        "ad_account_id": "act_12345",
        "api_version": "v23.0",
        "system_user_id": "201",
        "facebook_page_id": "301",
        "instagram_user_id": "401",
    }
    assert all(secret not in result.stdout for secret in SECRETS)


def test_environments_use_persists_and_current_reads_later_invocation(tmp_path):
    path = tmp_path / "environments.yaml"
    path.write_text(ENVIRONMENTS_YAML)
    env = {"META_CLI_ENVIRONMENTS_FILE": str(path)}

    selected = runner.invoke(app, ["environments", "use", "sandbox", "--json"], env=env)
    current = runner.invoke(app, ["environments", "current", "--json"], env=env)

    assert selected.exit_code == 0
    assert json.loads(selected.stdout)["environment"]["name"] == "sandbox"
    assert current.exit_code == 0
    assert json.loads(current.stdout)["name"] == "sandbox"
    assert "active_profile: sandbox" in path.read_text()
    combined_output = selected.stdout + current.stdout
    assert all(secret not in combined_output for secret in SECRETS)


def test_environments_empty_configuration_has_no_automatic_default(tmp_path):
    path = tmp_path / "missing.yaml"
    env = {"META_CLI_ENVIRONMENTS_FILE": str(path)}

    listed = runner.invoke(app, ["environments", "list"], env=env)
    current = runner.invoke(app, ["environments", "current"], env=env)

    assert listed.exit_code == 0
    assert "No Meta Ads environments configured" in listed.stdout
    assert current.exit_code == 1
    assert "No active Meta Ads environment is selected" in current.stdout
    assert "environments use <name>" in current.stdout
    assert not path.exists()


def test_environments_current_reports_missing_selection(tmp_path):
    path = tmp_path / "environments.yaml"
    path.write_text(ENVIRONMENTS_YAML)

    result = runner.invoke(
        app,
        ["environments", "current", "--json"],
        env={"META_CLI_ENVIRONMENTS_FILE": str(path)},
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "environments use <name>" in payload["error"]
    assert all(secret not in result.stdout for secret in SECRETS)


def test_environments_use_rejects_unknown_profile_actionably(tmp_path):
    path = tmp_path / "environments.yaml"
    path.write_text(ENVIRONMENTS_YAML)

    result = runner.invoke(
        app,
        ["environments", "use", "missing", "--json"],
        env={"META_CLI_ENVIRONMENTS_FILE": str(path)},
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert "Unknown Meta Ads environment 'missing'" in payload["error"]
    assert "production, sandbox" in payload["error"]
    assert "active_profile: null" in path.read_text()
    assert all(secret not in result.stdout for secret in SECRETS)


def test_settings_exposes_active_environment_without_secret_repr(tmp_path, monkeypatch):
    path = tmp_path / "environments.yaml"
    path.write_text(ENVIRONMENTS_YAML.replace("active_profile: null", "active_profile: production"))
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(path))
    monkeypatch.setenv("META_ACCESS_TOKEN", "legacy-token-never-print")
    monkeypatch.setenv("META_APP_ID", "legacy-app")
    monkeypatch.setenv("META_APP_SECRET", "legacy-secret-never-print")
    monkeypatch.setenv("META_AD_ACCOUNT_ID", "999")

    settings = load_settings()

    assert settings.active_environment == "production"
    representation = repr(settings)
    assert "production" in representation
    assert "legacy-token-never-print" not in representation
    assert "legacy-secret-never-print" not in representation
    assert all(secret not in representation for secret in SECRETS)
