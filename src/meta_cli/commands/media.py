from __future__ import annotations

from typing import Optional

import typer

from meta_cli.cli_utils import build_client, handle_cli_error
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit

app = typer.Typer(help="Media upload operations")


@app.command("upload-image")
def upload_image(
    path: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        result = client.upload_image(path)
        emit({"ok": True, "image": result}, as_json=json_output)
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("upload-video")
def upload_video(
    path: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        result = client.upload_video(path)
        emit({"ok": True, "video": result}, as_json=json_output)
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)
