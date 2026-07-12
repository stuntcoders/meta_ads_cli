from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
)

from meta_cli.exceptions import ConfigError

ENVIRONMENTS_FILE_ENV_VAR = "META_CLI_ENVIRONMENTS_FILE"
DEFAULT_API_VERSION = "v25.0"


class MetaAdsProfile(BaseModel):
    """Credentials and optional actor metadata for one named Meta Ads environment."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    access_token: SecretStr = Field(repr=False)
    app_id: str
    app_secret: SecretStr = Field(repr=False)
    ad_account_id: str
    api_version: str = DEFAULT_API_VERSION
    display_name: str | None = None
    system_user_id: str | None = None
    facebook_page_id: str | None = None
    instagram_user_id: str | None = None

    @field_validator("access_token", "app_secret")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Secret values cannot be empty")
        return value

    @field_validator(
        "app_id",
        "api_version",
        "display_name",
        "system_user_id",
        "facebook_page_id",
        "instagram_user_id",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty")
        return stripped

    @field_validator("ad_account_id", mode="before")
    @classmethod
    def validate_ad_account_id(cls, value: Any) -> str:
        account_id = str(value).strip()
        if account_id.startswith("act_") and account_id[4:].isdigit():
            return account_id
        if account_id.isdigit():
            return f"act_{account_id}"
        raise ValueError("ad_account_id must be numeric or start with 'act_'")

    def _storage_dict(self) -> dict[str, str]:
        """Return the on-disk representation; do not use this for display or logging."""
        data: dict[str, str] = {
            "access_token": self.access_token.get_secret_value(),
            "app_id": self.app_id,
            "app_secret": self.app_secret.get_secret_value(),
            "ad_account_id": self.ad_account_id,
            "api_version": self.api_version,
        }
        for key in (
            "display_name",
            "system_user_id",
            "facebook_page_id",
            "instagram_user_id",
        ):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        return data


class EnvironmentsFile(BaseModel):
    """Validated schema for the persistent named-environment file."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    active_profile: str | None = None
    profiles: dict[str, MetaAdsProfile] = Field(default_factory=dict)

    @field_validator("profiles")
    @classmethod
    def validate_profile_names(
        cls, profiles: dict[str, MetaAdsProfile]
    ) -> dict[str, MetaAdsProfile]:
        if any(not name.strip() or name != name.strip() for name in profiles):
            raise ValueError("Profile names cannot be empty or have surrounding whitespace")
        return profiles

    @field_validator("active_profile")
    @classmethod
    def validate_active_profile_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip() or value != value.strip():
            raise ValueError("active_profile cannot be empty or have surrounding whitespace")
        return value


class EnvironmentStore:
    """Load and safely update the user-local Meta Ads environment store."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path is not None else environments_file_path()

    def load(self) -> EnvironmentsFile:
        if not self.path.exists():
            return EnvironmentsFile()
        try:
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeError, yaml.YAMLError):
            raise ConfigError(f"Unable to read environments file: {self.path}") from None
        if not isinstance(raw, dict):
            raise ConfigError(f"Invalid environments file structure: {self.path}")
        try:
            config = EnvironmentsFile.model_validate(raw)
        except ValidationError:
            # Raise after leaving the handler: detailed validation context can contain input.
            config = None
        if config is None:
            raise ConfigError(f"Invalid environments file: {self.path}")
        return config

    def get_profile(self, name: str) -> MetaAdsProfile:
        config = self.load()
        try:
            return config.profiles[name]
        except KeyError:
            raise ConfigError(f"Meta Ads profile not found: {name}") from None

    def active_profile_name(self) -> str | None:
        return self.load().active_profile

    def get_active_profile(self) -> MetaAdsProfile | None:
        config = self.load()
        if config.active_profile is None:
            return None
        profile = config.profiles.get(config.active_profile)
        if profile is None:
            raise ConfigError(
                f"Active Meta Ads environment '{config.active_profile}' no longer exists. "
                "Select an available profile."
            )
        return profile

    def select_profile(self, name: str | None) -> EnvironmentsFile:
        """Persist a profile selection, or clear it when ``name`` is ``None``."""
        config = self.load()
        if name is not None and name not in config.profiles:
            raise ConfigError(f"Meta Ads profile not found: {name}")
        updated = EnvironmentsFile(active_profile=name, profiles=config.profiles)
        self._write(updated)
        return updated

    def _write(self, config: EnvironmentsFile) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = {
            "active_profile": config.active_profile,
            "profiles": {
                name: profile._storage_dict() for name, profile in config.profiles.items()
            },
        }
        serialized = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        temporary_path: Path | None = None
        try:
            fd, temp_name = tempfile.mkstemp(
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
            )
            temporary_path = Path(temp_name)
            # mkstemp creates the temporary file with owner-only permissions.
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
            os.chmod(self.path, 0o600)
        except OSError:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise ConfigError(f"Unable to write environments file: {self.path}") from None


def environments_file_path() -> Path:
    """Resolve the environment store path, honoring the explicit test/user override."""
    override = os.environ.get(ENVIRONMENTS_FILE_ENV_VAR)
    if override:
        return Path(override).expanduser()
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home).expanduser() if config_home else Path.home() / ".config"
    return base / "meta-ads-cli" / "environments.yaml"
