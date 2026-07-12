from __future__ import annotations

import json
from typing import Any, List, Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error, require_confirmation
from meta_cli.environments import EnvironmentStore
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit, print_table
from meta_cli.schemas import AdCreateConfig, load_yaml_model

app = typer.Typer(help="Ad operations")

AD_FIELDS = [
    "id",
    "name",
    "status",
    "effective_status",
    "adset_id",
    "campaign_id",
    "creative",
]

AD_DETAIL_FIELDS = [
    "id",
    "name",
    "status",
    "effective_status",
    "adset_id",
    "campaign_id",
    "creative",
    "tracking_specs",
    "created_time",
    "updated_time",
]


@app.command("list")
def list_ads(
    adset_id: Optional[str] = typer.Option(None, "--adset-id", help="Ad set ID"),
    all_ads: bool = typer.Option(False, "--all", help="List all account ads"),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    limit: int = typer.Option(100, min=1, max=1000, help="Maximum rows per request page"),
    after: Optional[str] = typer.Option(None, "--after", help="Cursor to fetch next page from"),
    before: Optional[str] = typer.Option(None, "--before", help="Cursor to fetch previous page from"),
    paginate: bool = typer.Option(True, "--paginate/--no-paginate", help="Auto-follow pagination"),
    max_pages: Optional[int] = typer.Option(None, "--max-pages", min=1, help="Maximum pages to fetch"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        if not all_ads and not adset_id:
            raise ValueError("Provide --all or --adset-id")
        if all_ads and adset_id:
            raise ValueError("Use either --all or --adset-id, not both")

        client = build_client(auth_config)
        if all_ads:
            result = client.list_all_ads(
                fields=AD_FIELDS,
                limit=limit,
                after=after,
                before=before,
                auto_paginate=paginate,
                max_pages=max_pages,
                include_paging=json_output,
            )
            title = "All Ads"
        else:
            result = client.list_ads(
                adset_id=adset_id,
                fields=AD_FIELDS,
                limit=limit,
                after=after,
                before=before,
                auto_paginate=paginate,
                max_pages=max_pages,
                include_paging=json_output,
            )
            title = f"Ads for Ad Set {adset_id}"

        if json_output:
            emit(result, as_json=True)
            return

        ads = result
        rows = [
            [
                item.get("id"),
                item.get("name"),
                item.get("status"),
                item.get("effective_status"),
                item.get("adset_id"),
                item.get("campaign_id"),
            ]
            for item in ads
        ]
        print_table(
            title,
            ["ID", "Name", "Status", "Effective", "AdSet", "Campaign"],
            rows,
            json_output,
            ads,
        )
    except (ConfigError, APIError, ValueError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("get")
def get_ad(
    ad_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        ad = client.get_ad_details(ad_id, fields=AD_DETAIL_FIELDS)
        if json_output:
            emit(ad, as_json=True)
            return

        rows = [[key, ad.get(key)] for key in AD_DETAIL_FIELDS]
        print_table(f"Ad {ad_id}", ["Field", "Value"], rows, False)
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("create")
def create_ad(
    config: Optional[str] = typer.Option(None, "--config", help="Path to ad YAML config"),
    adset_id: Optional[str] = typer.Option(None, "--adset-id", help="Ad set ID"),
    name: Optional[str] = typer.Option(None, "--name", help="Ad name"),
    page_id: Optional[str] = typer.Option(None, "--page-id", help="Facebook page ID"),
    instagram_actor_id: Optional[str] = typer.Option(
        None, "--instagram-actor-id", help="Legacy Instagram actor ID"
    ),
    instagram_user_id: Optional[str] = typer.Option(
        None, "--instagram-user-id", help="Instagram user ID for the object story"
    ),
    destination_url: Optional[str] = typer.Option(
        None, "--destination-url", help="Destination website URL"
    ),
    headlines: Optional[str] = typer.Option(
        None, "--headlines", help="Comma-separated headline variants"
    ),
    bodies: Optional[str] = typer.Option(
        None, "--bodies", help="Comma-separated body text variants"
    ),
    descriptions: Optional[str] = typer.Option(
        None, "--descriptions", help="Comma-separated description variants"
    ),
    image_hashes: Optional[str] = typer.Option(
        None, "--image-hashes", help="Comma-separated image hashes"
    ),
    image_assets_json: Optional[str] = typer.Option(
        None,
        "--image-assets-json",
        help='JSON array of placement image assets, e.g. [{"hash":"...","label":"feed_4x5"}]',
    ),
    asset_customization_rules_json: Optional[str] = typer.Option(
        None,
        "--asset-customization-rules-json",
        help="JSON array of placement customization rules",
    ),
    video_id: Optional[str] = typer.Option(None, "--video-id", help="Uploaded video ID"),
    call_to_action_type: str = typer.Option(
        "LEARN_MORE", "--call-to-action", help="Call to action type"
    ),
    status: str = typer.Option("PAUSED", "--status", help="Ad status"),
    existing_creative_id: Optional[str] = typer.Option(
        None, "--existing-creative-id", help="Use an existing creative ID"
    ),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and print payload only"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        ad_config = _build_ad_config(
            config=config,
            adset_id=adset_id,
            name=name,
            page_id=page_id,
            instagram_actor_id=instagram_actor_id,
            instagram_user_id=instagram_user_id,
            destination_url=destination_url,
            headlines=headlines,
            bodies=bodies,
            descriptions=descriptions,
            image_hashes=image_hashes,
            image_assets_json=image_assets_json,
            asset_customization_rules_json=asset_customization_rules_json,
            video_id=video_id,
            call_to_action_type=call_to_action_type,
            status=status,
            existing_creative_id=existing_creative_id,
            auth_config=auth_config,
        )

        creative_payload = None
        if not ad_config.existing_creative_id:
            creative_payload = ad_config.build_creative_payload()

        creative_id = ad_config.existing_creative_id
        ad_payload_preview = ad_config.build_ad_payload(creative_id=creative_id or "<creative_id>")

        if dry_run:
            emit(
                {
                    "ok": True,
                    "dry_run": True,
                    "uses_asset_feed_spec": ad_config.uses_asset_feed_spec(),
                    "creative_payload": creative_payload,
                    "ad_payload": ad_payload_preview,
                },
                as_json=json_output,
            )
            return

        client = build_client(auth_config)
        if not creative_id:
            creative_result = client.create_creative(creative_payload)
            creative_id = creative_result.get("id")
            if not creative_id:
                raise APIError("Creative created but no creative ID was returned")
        ad_payload = ad_config.build_ad_payload(creative_id=creative_id)
        ad_result = client.create_ad(ad_payload)
        emit(
            {
                "ok": True,
                "ad": ad_result,
                "creative_id": creative_id,
                "uses_asset_feed_spec": ad_config.uses_asset_feed_spec(),
            },
            as_json=json_output,
        )
    except (ConfigError, APIError, ValueError, json.JSONDecodeError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("update-creative")
def update_ad_creative(
    ad_id: str,
    creative_id: str = typer.Option(..., "--creative-id", help="Creative ID to attach to the ad"),
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show action without updating"),
) -> None:
    try:
        require_confirmation(
            f"Update ad {ad_id} to use creative {creative_id}?",  # spend-affecting change
            yes=yes,
        )
        if dry_run:
            emit(
                {
                    "ok": True,
                    "dry_run": True,
                    "ad_id": ad_id,
                    "creative_id": creative_id,
                },
                as_json=json_output,
            )
            return

        client = build_client(auth_config)
        result = client.update_ad_creative(ad_id, creative_id)
        emit(
            {"ok": True, "ad_id": ad_id, "creative_id": creative_id, "result": result},
            as_json=json_output,
        )
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("pause")
def pause_ad(
    ad_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show action without updating"),
) -> None:
    _change_status(ad_id, "PAUSED", auth_config, yes, json_output, dry_run)


@app.command("resume")
def resume_ad(
    ad_id: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show action without updating"),
) -> None:
    _change_status(ad_id, "ACTIVE", auth_config, yes, json_output, dry_run)


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_json_list(value: Optional[str], flag_name: str) -> List[Any]:
    if not value:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError(f"{flag_name} must be a JSON array")
    return parsed


def _build_ad_config(
    config: Optional[str],
    adset_id: Optional[str],
    name: Optional[str],
    page_id: Optional[str],
    instagram_actor_id: Optional[str],
    instagram_user_id: Optional[str],
    destination_url: Optional[str],
    headlines: Optional[str],
    bodies: Optional[str],
    descriptions: Optional[str],
    image_hashes: Optional[str],
    image_assets_json: Optional[str],
    asset_customization_rules_json: Optional[str],
    video_id: Optional[str],
    call_to_action_type: str,
    status: str,
    existing_creative_id: Optional[str],
    auth_config: Optional[str],
) -> AdCreateConfig:
    if config:
        return load_yaml_model(
            config,
            AdCreateConfig,
            defaults=lambda data: _profile_ad_identity_defaults(
                auth_config=auth_config,
                page_id=data.get("page_id"),
                instagram_actor_id=data.get("instagram_actor_id"),
                instagram_user_id=data.get("instagram_user_id"),
                existing_creative_id=data.get("existing_creative_id"),
            ),
        )

    identity_defaults = _profile_ad_identity_defaults(
        auth_config=auth_config,
        page_id=page_id,
        instagram_actor_id=instagram_actor_id,
        instagram_user_id=instagram_user_id,
        existing_creative_id=existing_creative_id,
    )
    return AdCreateConfig(
        adset_id=adset_id,
        name=name,
        page_id=page_id if page_id is not None else identity_defaults.get("page_id"),
        instagram_actor_id=instagram_actor_id,
        instagram_user_id=(
            instagram_user_id
            if instagram_user_id is not None
            else identity_defaults.get("instagram_user_id")
        ),
        destination_url=destination_url,
        headlines=_split_csv(headlines),
        bodies=_split_csv(bodies),
        descriptions=_split_csv(descriptions),
        image_hashes=_split_csv(image_hashes),
        image_assets=_parse_json_list(image_assets_json, "--image-assets-json"),
        asset_customization_rules=_parse_json_list(
            asset_customization_rules_json, "--asset-customization-rules-json"
        ),
        video_id=video_id,
        call_to_action_type=call_to_action_type,
        status=status,
        existing_creative_id=existing_creative_id,
    )


def _profile_ad_identity_defaults(
    *,
    auth_config: Optional[str],
    page_id: Any,
    instagram_actor_id: Any,
    instagram_user_id: Any,
    existing_creative_id: Any,
) -> dict[str, str]:
    """Return missing ad identity values from the selected named environment."""
    if auth_config is not None or existing_creative_id:
        return {}
    needs_page = page_id is None
    needs_instagram = instagram_actor_id is None and instagram_user_id is None
    if not needs_page and not needs_instagram:
        return {}

    profile = EnvironmentStore().get_active_profile()
    if profile is None:
        return {}

    defaults: dict[str, str] = {}
    if needs_page and profile.facebook_page_id:
        defaults["page_id"] = profile.facebook_page_id
    if needs_instagram and profile.instagram_user_id:
        defaults["instagram_user_id"] = profile.instagram_user_id
    return defaults


def _change_status(
    ad_id: str,
    status: str,
    auth_config: Optional[str],
    yes: bool,
    json_output: bool,
    dry_run: bool,
) -> None:
    try:
        require_confirmation(f"Set ad {ad_id} to {status}?", yes=yes)
        if dry_run:
            emit({"ok": True, "dry_run": True, "ad_id": ad_id, "status": status}, as_json=json_output)
            return
        client = build_client(auth_config)
        result = client.update_ad_status(ad_id, status)
        emit({"ok": True, "ad_id": ad_id, "status": status, "result": result}, as_json=json_output)
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)
