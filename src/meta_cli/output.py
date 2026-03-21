from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console

console = Console()


def emit(data: Any, as_json: bool = False) -> None:
    if as_json:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        if isinstance(data, str):
            console.print(data)
        else:
            console.print(data)
