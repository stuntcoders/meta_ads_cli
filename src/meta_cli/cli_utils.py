from __future__ import annotations

from typing import Optional

import typer

from meta_cli.config import load_settings
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit
from meta_cli.sdk import MetaSDKClient


def build_client(auth_config: Optional[str] = None) -> MetaSDKClient:
    settings = load_settings(auth_config)
    return MetaSDKClient(settings.credentials)


def handle_cli_error(exc: Exception, as_json: bool = False) -> None:
    emit({"ok": False, "error": str(exc)}, as_json=as_json)
    raise typer.Exit(code=1) from exc


def require_confirmation(message: str, yes: bool) -> None:
    if yes:
        return
    confirmed = typer.confirm(message)
    if not confirmed:
        raise typer.Exit(code=1)


def wrap_command(func):
    def _wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ConfigError, APIError, ValueError) as exc:
            json_output = kwargs.get("json_output", False)
            handle_cli_error(exc, as_json=json_output)

    return _wrapped
