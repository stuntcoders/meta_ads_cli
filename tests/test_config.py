from __future__ import annotations

import pytest

from meta_cli.config import load_settings
from meta_cli.exceptions import ConfigError


@pytest.fixture(autouse=True)
def clear_meta_env(monkeypatch):
    for key in [
        "META_ACCESS_TOKEN",
        "META_APP_ID",
        "META_APP_SECRET",
        "META_AD_ACCOUNT_ID",
        "META_API_VERSION",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_load_settings_from_env(monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN", "token")
    monkeypatch.setenv("META_APP_ID", "app")
    monkeypatch.setenv("META_APP_SECRET", "secret")
    monkeypatch.setenv("META_AD_ACCOUNT_ID", "123456")

    settings = load_settings()

    assert settings.credentials.ad_account_id == "act_123456"
    assert settings.credentials.api_version == "v20.0"


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
    assert settings.credentials.api_version == "v21.0"


def test_missing_required_values_raises():
    with pytest.raises(ConfigError):
        load_settings()
