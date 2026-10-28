"""Collision-safe output path resolution and summary formatting utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


def get_safe_output_path(
    source_path: str | Path,
    new_ext: str | None = None,
    suffix: str = "",
) -> Path:
    """Return a non-colliding output path in the same directory as `source_path`.

    Never overwrites an existing file; automatically increments `name (1).ext`, `name (2).ext`, etc.
    """
    src = Path(source_path)
    parent = src.parent
    stem = f"{src.stem}{suffix}"
    ext = new_ext if new_ext is not None else src.suffix
    if ext and not ext.startswith("."):
        ext = f".{ext}"

    candidate = parent / f"{stem}{ext}"
    counter = 1
    while candidate.exists():
        candidate = parent / f"{stem} ({counter}){ext}"
        counter += 1
    return candidate


def format_saved_summary(outputs: Sequence[str | Path]) -> str:
    """Format a concise toast notification summary for one or more saved files."""
    if not outputs:
        return "Completed"
    first_name = Path(outputs[0]).name
    if len(outputs) == 1:
        return f"Saved {first_name}"
    return f"Saved {len(outputs)} files ({first_name}…)"
