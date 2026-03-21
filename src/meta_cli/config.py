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


def load_settings(config_path: str | None = None) -> Settings:
    file_data: dict[str, Any] = {}
    if config_path:
        file_data = _read_yaml_config(Path(config_path))

    merged = {**file_data, **os.environ}

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
