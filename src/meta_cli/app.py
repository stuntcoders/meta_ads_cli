from __future__ import annotations

import typer

from meta_cli.commands.ads import app as ads_app
from meta_cli.commands.adsets import app as adsets_app
from meta_cli.commands.auth import app as auth_app
from meta_cli.commands.campaigns import app as campaigns_app
from meta_cli.commands.insights import app as insights_app
from meta_cli.commands.media import app as media_app
from meta_cli.logging_utils import configure_logging

app = typer.Typer(help="Meta Ads management CLI")
app.add_typer(auth_app, name="auth")
app.add_typer(campaigns_app, name="campaigns")
app.add_typer(adsets_app, name="adsets")
app.add_typer(ads_app, name="ads")
app.add_typer(insights_app, name="insights")
app.add_typer(media_app, name="media")


@app.callback()
def main(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
) -> None:
    configure_logging(debug)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
