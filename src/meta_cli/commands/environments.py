from __future__ import annotations

import typer

from meta_cli.environments import EnvironmentStore, MetaAdsProfile
from meta_cli.exceptions import ConfigError
from meta_cli.output import emit, print_table

app = typer.Typer(help="Inspect and select named Meta Ads environments")


def _profile_identity(name: str, profile: MetaAdsProfile, active: bool) -> dict[str, object]:
    """Build the only profile representation that commands may display."""
    return {
        "name": name,
        "active": active,
        "display_name": profile.display_name,
        "ad_account_id": profile.ad_account_id,
        "api_version": profile.api_version,
        "system_user_id": profile.system_user_id,
        "facebook_page_id": profile.facebook_page_id,
        "instagram_user_id": profile.instagram_user_id,
    }


def _fail(message: str, json_output: bool) -> None:
    emit({"ok": False, "error": message}, as_json=json_output)
    raise typer.Exit(code=1)


@app.command("list")
def list_environments(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """List configured environments without displaying credentials."""
    try:
        config = EnvironmentStore().load()
    except ConfigError as exc:
        _fail(str(exc), json_output)

    identities = [
        _profile_identity(name, profile, name == config.active_profile)
        for name, profile in sorted(config.profiles.items())
    ]
    if json_output:
        emit(identities, as_json=True)
        return
    if not identities:
        emit("No Meta Ads environments configured.")
        return
    print_table(
        "Meta Ads environments",
        ["Active", "Name", "Display name", "Ad account", "API version"],
        [
            (
                "*" if identity["active"] else "",
                identity["name"],
                identity["display_name"],
                identity["ad_account_id"],
                identity["api_version"],
            )
            for identity in identities
        ],
    )


@app.command("current")
def current_environment(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Show the explicitly selected environment without displaying credentials."""
    try:
        config = EnvironmentStore().load()
    except ConfigError as exc:
        _fail(str(exc), json_output)
    if config.active_profile is None:
        _fail(
            "No active Meta Ads environment is selected. "
            "Run 'meta-cli environments use <name>' to select one.",
            json_output,
        )
    if config.active_profile not in config.profiles:
        _fail(
            f"Active Meta Ads environment '{config.active_profile}' no longer exists. "
            "Run 'meta-cli environments list' and "
            "'meta-cli environments use <name>' to select an available profile.",
            json_output,
        )

    identity = _profile_identity(
        config.active_profile,
        config.profiles[config.active_profile],
        active=True,
    )
    if json_output:
        emit(identity, as_json=True)
        return
    print_table(
        "Current Meta Ads environment",
        ["Name", "Display name", "Ad account", "API version"],
        [
            (
                identity["name"],
                identity["display_name"],
                identity["ad_account_id"],
                identity["api_version"],
            )
        ],
    )


@app.command("use")
def use_environment(
    name: str = typer.Argument(..., help="Configured environment name"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Persist an explicit environment selection."""
    store = EnvironmentStore()
    try:
        config = store.load()
        if name not in config.profiles:
            available = ", ".join(sorted(config.profiles)) or "none"
            _fail(
                f"Unknown Meta Ads environment '{name}'. Available environments: {available}. "
                "Add the profile to the environments file or choose a listed name.",
                json_output,
            )
        store.select_profile(name)
    except ConfigError as exc:
        _fail(str(exc), json_output)

    identity = _profile_identity(name, config.profiles[name], active=True)
    if json_output:
        emit({"ok": True, "environment": identity}, as_json=True)
        return
    emit(f"Active Meta Ads environment set to '{name}'.")
