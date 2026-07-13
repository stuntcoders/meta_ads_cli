from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import typer
import yaml

from meta_cli.config import load_environments_store, save_environments_store
from meta_cli.exceptions import ConfigError
from meta_cli.output import emit, print_table

app = typer.Typer(help="Environment profile commands")


def _default_environments_file(path: Optional[str] = None) -> Path:
    if path:
        return Path(path)
    configured = os.environ.get("META_CLI_ENVIRONMENTS_FILE")
    if configured:
        return Path(configured)
    return Path.cwd() / ".meta-ads-environments.yml"


def _profile_summary(name: str, profile: dict[str, Any], active_profile: str | None) -> dict[str, Any]:
    return {
        "name": name,
        "active": name == active_profile,
        "display_name": profile.get("display_name"),
        "ad_account_id": profile.get("ad_account_id"),
        "api_version": profile.get("api_version"),
        "has_access_token": bool(profile.get("access_token")),
        "has_app_id": bool(profile.get("app_id")),
        "has_app_secret": bool(profile.get("app_secret")),
        "has_system_user_id": bool(profile.get("system_user_id")),
        "has_facebook_page_id": bool(profile.get("facebook_page_id")),
        "has_instagram_user_id": bool(profile.get("instagram_user_id")),
    }


def _handle_error(exc: Exception, json_output: bool = False) -> None:
    emit({"ok": False, "error": str(exc)}, as_json=json_output)
    raise typer.Exit(code=1) from exc


@app.command("list")
def list_environments(
    file: Optional[str] = typer.Option(None, "--file", help="Path to environments YAML file"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """List configured environment profiles without revealing secrets."""
    try:
        path = _default_environments_file(file)
        store = load_environments_store(path)
        profiles = store.get("profiles", {})
        active_profile = store.get("active_profile")
        rows = [
            _profile_summary(name, profile, active_profile)
            for name, profile in sorted(profiles.items())
        ]
        if json_output:
            emit({"ok": True, "file": str(path), "active_profile": active_profile, "profiles": rows}, as_json=True)
            return
        print_table(
            "Meta Ads environments",
            ["Name", "Active", "Display name", "Ad account", "API version"],
            [
                [
                    row["name"],
                    "yes" if row["active"] else "",
                    row.get("display_name") or "",
                    row.get("ad_account_id") or "",
                    row.get("api_version") or "",
                ]
                for row in rows
            ],
        )
    except ConfigError as exc:
        _handle_error(exc, json_output)


@app.command("current")
def current_environment(
    file: Optional[str] = typer.Option(None, "--file", help="Path to environments YAML file"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Show the active environment profile without revealing secrets."""
    try:
        path = _default_environments_file(file)
        store = load_environments_store(path)
        active_profile = store.get("active_profile")
        profiles = store.get("profiles", {})
        if not active_profile:
            raise ConfigError("No active environment profile is selected")
        if active_profile not in profiles:
            raise ConfigError(f"Active environment profile not found: {active_profile}")
        row = _profile_summary(active_profile, profiles[active_profile], active_profile)
        if json_output:
            emit({"ok": True, "file": str(path), "profile": row}, as_json=True)
            return
        print_table(
            "Current Meta Ads environment",
            ["Name", "Display name", "Ad account", "API version"],
            [[row["name"], row.get("display_name") or "", row.get("ad_account_id") or "", row.get("api_version") or ""]],
        )
    except ConfigError as exc:
        _handle_error(exc, json_output)


@app.command("use")
def use_environment(
    profile: str = typer.Argument(..., help="Environment profile name to select"),
    file: Optional[str] = typer.Option(None, "--file", help="Path to environments YAML file"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Select the active environment profile."""
    try:
        path = _default_environments_file(file)
        store = load_environments_store(path)
        profiles = store.get("profiles", {})
        if profile not in profiles:
            available = ", ".join(sorted(profiles)) or "none"
            raise ConfigError(f"Environment profile not found: {profile}. Available profiles: {available}")
        store["active_profile"] = profile
        save_environments_store(path, store)
        summary = _profile_summary(profile, profiles[profile], profile)
        if json_output:
            emit({"ok": True, "file": str(path), "profile": summary}, as_json=True)
            return
        emit(f"Selected Meta Ads environment: {profile}")
    except (ConfigError, yaml.YAMLError) as exc:
        _handle_error(exc, json_output)
