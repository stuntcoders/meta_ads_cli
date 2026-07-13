from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from meta_cli.exceptions import ConfigError


class MetaCredentials(BaseModel):
    access_token: str = Field(alias="META_ACCESS_TOKEN")
    app_id: str = Field(alias="META_APP_ID")
    app_secret: str = Field(alias="META_APP_SECRET")
    ad_account_id: str = Field(alias="META_AD_ACCOUNT_ID")
    api_version: str = Field(default="v20.0", alias="META_API_VERSION")
    system_user_id: str | None = Field(default=None, alias="META_SYSTEM_USER_ID")
    facebook_page_id: str | None = Field(default=None, alias="META_FACEBOOK_PAGE_ID")
    instagram_user_id: str | None = Field(default=None, alias="META_INSTAGRAM_USER_ID")

    @field_validator("ad_account_id")
    @classmethod
    def validate_ad_account_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("META_AD_ACCOUNT_ID cannot be empty")
        if value.startswith("act_"):
            return value
        if value.isdigit():
            return f"act_{value}"
        raise ValueError("META_AD_ACCOUNT_ID must be numeric or start with 'act_'")


class Settings(BaseModel):
    credentials: MetaCredentials


def _read_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in config file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping")
    return data


def load_environments_store(path: Path) -> dict[str, Any]:
    data = _read_yaml_config(path)
    profiles = data.get("profiles")
    if profiles is None:
        raise ConfigError("Environments file must contain a profiles mapping")
    if not isinstance(profiles, dict):
        raise ConfigError("Environments profiles must be a mapping")
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ConfigError(f"Environment profile must be a mapping: {name}")
    return data


def save_environments_store(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _load_active_environment() -> dict[str, Any]:
    env_path = os.environ.get("META_CLI_ENVIRONMENTS_FILE")
    if not env_path:
        return {}
    store = load_environments_store(Path(env_path))
    active_profile = store.get("active_profile")
    profiles = store.get("profiles", {})
    if not active_profile:
        raise ConfigError("No active environment profile is selected")
    if active_profile not in profiles:
        raise ConfigError(f"Active environment profile not found: {active_profile}")
    profile = profiles[active_profile]
    profile_map = {
        "access_token": "META_ACCESS_TOKEN",
        "app_id": "META_APP_ID",
        "app_secret": "META_APP_SECRET",
        "ad_account_id": "META_AD_ACCOUNT_ID",
        "api_version": "META_API_VERSION",
        "system_user_id": "META_SYSTEM_USER_ID",
        "facebook_page_id": "META_FACEBOOK_PAGE_ID",
        "instagram_user_id": "META_INSTAGRAM_USER_ID",
    }
    return {env_key: profile[value_key] for value_key, env_key in profile_map.items() if value_key in profile}


def load_settings(config_path: str | None = None) -> Settings:
    file_data: dict[str, Any] = {}
    if config_path:
        file_data = _read_yaml_config(Path(config_path))

    environment_data = _load_active_environment()
    merged = {**environment_data, **file_data, **os.environ}

    try:
        creds = MetaCredentials.model_validate(merged)
    except ValidationError as exc:
        missing = []
        for error in exc.errors():
            key = error.get("loc", [""])[0]
            missing.append(str(key))
        pretty_keys = ", ".join(sorted(set(missing)))
        raise ConfigError(
            "Missing or invalid Meta credentials. Ensure these are set via env or config: "
            f"{pretty_keys}"
        ) from exc

    return Settings(credentials=creds)
