from __future__ import annotations

import json
from typing import Any, Iterable, List, Sequence

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def emit(data: Any, as_json: bool = False) -> None:
    if as_json:
        typer.echo(json.dumps(data, indent=2, default=str))
        return
    if isinstance(data, str):
        console.print(data)
    else:
        console.print(data)


def render_table(title: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> Table:
    table = Table(title=title)
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*["" if value is None else str(value) for value in row])
    return table


def print_table(
    title: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    as_json: bool = False,
    raw: List[dict[str, Any]] | None = None,
) -> None:
    if as_json:
        emit(raw if raw is not None else [], as_json=True)
        return
    emit(render_table(title=title, columns=columns, rows=rows))
