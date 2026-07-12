from __future__ import annotations

import pytest

from meta_cli.config import load_settings
from meta_cli.exceptions import ConfigError


@pytest.fixture(autouse=True)
def clear_meta_env(monkeypatch, tmp_path):
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(tmp_path / "environments.yaml"))
    for key in [
        "META_ACCESS_TOKEN",
        "META_APP_ID",
        "META_APP_SECRET",
        "META_AD_ACCOUNT_ID",
        "META_API_VERSION",
        "META_SYSTEM_USER_ID",
        "META_FACEBOOK_PAGE_ID",
        "META_INSTAGRAM_USER_ID",
        "META_CLI_ENVIRONMENTS_FILE",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_load_settings_from_selected_environment(tmp_path, monkeypatch):
    environments = tmp_path / "environments.yaml"
    environments.write_text(
        """
active_profile: sandbox
profiles:
  sandbox:
    access_token: selected-token
    app_id: selected-app
    app_secret: selected-secret
    ad_account_id: 123456
""".strip()
    )
    monkeypatch.setenv("META_CLI_ENVIRONMENTS_FILE", str(environments))

    settings = load_settings()

    assert settings.active_environment == "sandbox"
    assert settings.credentials.access_token == "selected-token"
    assert settings.credentials.ad_account_id == "act_123456"
    assert settings.credentials.api_version == "v25.0"


def test_env_overrides_file(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text(
        """
META_ACCESS_TOKEN: file-token
META_APP_ID: file-app
META_APP_SECRET: file-secret
META_AD_ACCOUNT_ID: 999
META_API_VERSION: v21.0
""".strip()
    )
    monkeypatch.setenv("META_ACCESS_TOKEN", "env-token")
    monkeypatch.setenv("META_APP_ID", "env-app")
    monkeypatch.setenv("META_APP_SECRET", "env-secret")
    monkeypatch.setenv("META_AD_ACCOUNT_ID", "123")

    settings = load_settings(str(config))

    assert settings.credentials.access_token == "env-token"
    assert settings.credentials.app_id == "env-app"
    assert settings.credentials.app_secret == "env-secret"
    assert settings.credentials.ad_account_id == "act_123"
    # Unset compatible values continue to come from the explicit legacy file.
    assert settings.credentials.api_version == "v21.0"


def test_ambient_credentials_do_not_replace_profile_selection(monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN", "ambient-token")
    monkeypatch.setenv("META_APP_ID", "ambient-app")
    monkeypatch.setenv("META_APP_SECRET", "ambient-secret")
    monkeypatch.setenv("META_AD_ACCOUNT_ID", "123")

    with pytest.raises(ConfigError, match="No active Meta Ads environment"):
        load_settings()


def test_missing_selection_is_actionable():
    with pytest.raises(ConfigError, match="environments use <name>"):
        load_settings()
