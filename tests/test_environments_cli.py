from __future__ import annotations

import yaml
from typer.testing import CliRunner

from meta_cli.app import app
from meta_cli.config import load_settings

runner = CliRunner()


def _write_store(path):
    path.write_text(
        yaml.safe_dump(
            {
                "active_profile": "brand-a",
                "profiles": {
                    "brand-a": {
                        "display_name": "Brand A",
                        "access_token": "token-a",
                        "app_id": "app-a",
                        "app_secret": "secret-a",
                        "ad_account_id": "123",
                        "api_version": "v25.0",
                        "facebook_page_id": "page-a",
                    },
                    "brand-b": {
                        "display_name": "Brand B",
                        "access_token": "token-b",
                        "app_id": "app-b",
                        "app_secret": "secret-b",
                        "ad_account_id": "act_456",
                    },
                },
            },
            sort_keys=False,
        )
    )


def test_environments_list_masks_secret_fields(tmp_path):
    config = tmp_path / "environments.yml"
    _write_store(config)

    result = runner.invoke(app, ["environments", "list", "--file", str(config), "--json"])

    assert result.exit_code == 0
    assert '"active_profile": "brand-a"' in result.stdout
    assert '"has_access_token": true' in result.stdout.lower()
    assert "token-a" not in result.stdout
    assert "secret-a" not in result.stdout


def test_environments_current_requires_active_profile(tmp_path):
    config = tmp_path / "environments.yml"
    config.write_text(yaml.safe_dump({"active_profile": None, "profiles": {"brand-a": {}}}))

    result = runner.invoke(app, ["environments", "current", "--file", str(config), "--json"])

    assert result.exit_code == 1
    assert "No active environment profile" in result.stdout


def test_environments_use_updates_active_profile(tmp_path):
    config = tmp_path / "environments.yml"
    _write_store(config)

    result = runner.invoke(app, ["environments", "use", "brand-b", "--file", str(config), "--json"])

    assert result.exit_code == 0
    data = yaml.safe_load(config.read_text())
    assert data["active_profile"] == "brand-b"
    assert "token-b" not in result.stdout


def test_load_settings_from_active_environment_file(tmp_path, monkeypatch):
    config = tmp_path / "environments.yml"
    _write_store(config)
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(config))

    settings = load_settings()

    assert settings.credentials.access_token == "token-a"
    assert settings.credentials.ad_account_id == "act_123"
    assert settings.credentials.api_version == "v25.0"
    assert settings.credentials.facebook_page_id == "page-a"
