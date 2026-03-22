from __future__ import annotations

from typing import Any, Dict, Optional

import typer
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from meta_cli.cli_utils import build_client, handle_cli_error
from meta_cli.exceptions import APIError, ConfigError
from meta_cli.output import console, emit

app = typer.Typer(help="Media upload operations")


@app.command("upload-image")
def upload_image(
    path: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)
        if json_output:
            result = client.upload_image(path)
            emit({"ok": True, "image": result}, as_json=True)
            return

        with console.status(f"Uploading image from {path}..."):
            result = client.upload_image(path)

        emit("✅ Image upload completed")
        emit({"ok": True, "image": result}, as_json=False)
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


@app.command("upload-video")
def upload_video(
    path: str,
    auth_config: Optional[str] = typer.Option(None, "--auth-config", help="Path to auth YAML"),
    wait: bool = typer.Option(
        True,
        "--wait/--no-wait",
        help="Wait for video processing completion after upload",
    ),
    poll_interval: float = typer.Option(
        5.0,
        "--poll-interval",
        min=0.1,
        help="Polling interval in seconds while waiting for processing",
    ),
    timeout: int = typer.Option(
        1800,
        "--timeout",
        min=1,
        help="Max seconds to wait for processing completion",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    try:
        client = build_client(auth_config)

        if json_output:
            upload_result = client.upload_video(path)
            payload: Dict[str, Any] = {"ok": True, "video": upload_result}
            if wait:
                video_id = _extract_video_id(upload_result)
                payload["processing"] = client.wait_for_video_processing(
                    video_id=video_id,
                    poll_interval=poll_interval,
                    timeout=timeout,
                )
            emit(payload, as_json=True)
            return

        with console.status(f"Uploading video from {path}..."):
            upload_result = client.upload_video(path)

        video_id = _extract_video_id(upload_result)
        emit(f"✅ Video upload completed (video_id={video_id})")

        if not wait:
            emit({"ok": True, "video": upload_result}, as_json=False)
            emit(
                "ℹ️ Skipping processing wait (--no-wait). "
                "Use upload-video without --no-wait to track processing completion."
            )
            return

        processing_result = _wait_with_progress(
            client=client,
            video_id=video_id,
            poll_interval=poll_interval,
            timeout=timeout,
        )
        emit("✅ Video processing completed")
        emit(
            {"ok": True, "video": upload_result, "processing": processing_result},
            as_json=False,
        )
    except (ConfigError, APIError) as exc:
        handle_cli_error(exc, as_json=json_output)


def _extract_video_id(upload_result: Dict[str, Any]) -> str:
    video_id = upload_result.get("id") or upload_result.get("video_id")
    if not video_id:
        raise APIError("Video upload succeeded but no video id was returned by Meta")
    return str(video_id)


def _wait_with_progress(
    client,
    video_id: str,
    poll_interval: float,
    timeout: int,
) -> Dict[str, Any]:
    last_state = "unknown"
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Processing video...", total=100)

        def _on_update(snapshot: Dict[str, Any]) -> None:
            nonlocal last_state
            progress_value = snapshot.get("progress")
            state = snapshot.get("state", "unknown")
            last_state = state
            description = f"Processing video ({state})"
            if isinstance(progress_value, int):
                bounded = max(0, min(progress_value, 100))
                progress.update(task_id, description=description, completed=bounded)
            else:
                progress.update(task_id, description=description)

        result = client.wait_for_video_processing(
            video_id=video_id,
            poll_interval=poll_interval,
            timeout=timeout,
            on_update=_on_update,
        )
        progress.update(task_id, description=f"Processing video ({last_state})", completed=100)
        return result
