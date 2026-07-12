from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from meta_cli.environments import EnvironmentStore
from meta_cli.exceptions import ConfigError


class MetaCredentials(BaseModel):
    access_token: str = Field(alias="META_ACCESS_TOKEN", repr=False)
    app_id: str = Field(alias="META_APP_ID")
    app_secret: str = Field(alias="META_APP_SECRET", repr=False)
    ad_account_id: str = Field(alias="META_AD_ACCOUNT_ID")
    api_version: str = Field(default="v20.0", alias="META_API_VERSION")

    @field_validator("ad_account_id", mode="before")
    @classmethod
    def validate_ad_account_id(cls, value: Any) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("META_AD_ACCOUNT_ID cannot be empty")
        if value.startswith("act_"):
            return value
        if value.isdigit():
            return f"act_{value}"
        raise ValueError("META_AD_ACCOUNT_ID must be numeric or start with 'act_'")


class Settings(BaseModel):
    credentials: MetaCredentials
    active_environment: str | None = None


def _read_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        # Parser details may echo nearby credential values from malformed files.
        raise ConfigError(f"Invalid YAML in config file: {path}") from None
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping")
    return data


def _validate_legacy_credentials(data: dict[str, Any]) -> MetaCredentials:
    try:
        return MetaCredentials.model_validate(data)
    except ValidationError as exc:
        keys = {str(error.get("loc", [""])[0]) for error in exc.errors()}
        raise ConfigError(
            "Missing or invalid Meta credentials in the explicit legacy auth configuration. "
            "Ensure these are set via the YAML file or META_* environment overrides: "
            f"{', '.join(sorted(keys))}"
        ) from None


def load_settings(config_path: str | None = None) -> Settings:
    if config_path is not None:
        # Flat META_* keys and credential environment overrides intentionally remain
        # available only when the operator supplies an explicit legacy auth file.
        file_data = _read_yaml_config(Path(config_path))
        credentials = _validate_legacy_credentials({**file_data, **os.environ})
        return Settings(credentials=credentials, active_environment=None)

    store = EnvironmentStore()
    config = store.load()
    if config.active_profile is None:
        if config.profiles:
            guidance = "Run 'meta-cli environments use <name>' to select one."
        else:
            guidance = (
                f"Add a profile to {store.path}, then run "
                "'meta-cli environments use <name>' to select it."
            )
        raise ConfigError(f"No active Meta Ads environment is selected. {guidance}")

    profile = config.profiles.get(config.active_profile)
    if profile is None:
        raise ConfigError(
            f"Active Meta Ads environment '{config.active_profile}' no longer exists. "
            "Run 'meta-cli environments list' and "
            "'meta-cli environments use <name>' to select an available profile."
        )

    credentials = MetaCredentials.model_validate(
        {
            "META_ACCESS_TOKEN": profile.access_token.get_secret_value(),
            "META_APP_ID": profile.app_id,
            "META_APP_SECRET": profile.app_secret.get_secret_value(),
            "META_AD_ACCOUNT_ID": profile.ad_account_id,
            "META_API_VERSION": profile.api_version,
        }
    )
    return Settings(credentials=credentials, active_environment=config.active_profile)
