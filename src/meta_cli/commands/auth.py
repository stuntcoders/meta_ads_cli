from __future__ import annotations

from typing import Optional

import typer

from meta_cli.config import load_settings
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import emit
from meta_cli.sdk import MetaSDKClient

app = typer.Typer(help="Authentication and credential commands")


def _safe_auth_error(exc: Exception, settings: object | None) -> str:
    message = str(exc)
    if settings is None:
        return message
    credentials = getattr(settings, "credentials", None)
    if credentials is None:
        return message
    for secret in (credentials.access_token, credentials.app_secret):
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message


@app.command("test")
def auth_test(
    config: Optional[str] = typer.Option(None, "--config", help="Path to optional YAML config file"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Validate Meta credentials and ad account access."""
    settings = None
    try:
        settings = load_settings(config)
        client = MetaSDKClient(settings.credentials)
        result = client.test_auth()
        if json_output:
            emit({"ok": True, "account": result}, as_json=True)
            return
        emit("✅ Authentication successful")
        emit(f"Account: {result['name']} ({result['id']}) status={result['account_status']}")
    except (ConfigError, APIError) as exc:
        emit({"ok": False, "error": _safe_auth_error(exc, settings)}, as_json=json_output)
        raise typer.Exit(code=1) from exc
