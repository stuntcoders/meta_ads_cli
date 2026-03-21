from __future__ import annotations

import typer

from meta_cli.commands.auth import app as auth_app
from meta_cli.logging_utils import configure_logging

app = typer.Typer(help="Meta Ads management CLI")
app.add_typer(auth_app, name="auth")


@app.callback()
def main(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
) -> None:
    configure_logging(debug)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
