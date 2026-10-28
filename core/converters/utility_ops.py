"""Quick file utilities: Clipboard paths/names, file duplication, ZIP packaging, and SHA-256."""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path
from typing import Sequence

from core.converters.path_utils import format_saved_summary, get_safe_output_path
from core.models import ConversionResult

UTILITY_ACTION_IDS: frozenset[str] = frozenset({
    "util_copy_path",
    "util_copy_name",
    "util_sha256",
    "util_duplicate",
    "pack_zip",
})


def run_utility_action(
    action_id: str,
    action_label: str,
    paths: Sequence[str],
) -> ConversionResult:
    """Execute a file utility or batch archive action and return a `ConversionResult`."""
    if action_id == "util_copy_path":
        clip = "\n".join(paths)
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=list(paths),
            clipboard_text=clip,
            summary_text=f"Copied {len(paths)} path{'s' if len(paths) > 1 else ''} to clipboard",
        )

    if action_id == "util_copy_name":
        names = [Path(p).name for p in paths]
        clip = "\n".join(names)
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=list(paths),
            clipboard_text=clip,
            summary_text=f"Copied {len(names)} filename{'s' if len(names) > 1 else ''}",
        )

    if action_id == "util_sha256":
        lines: list[str] = []
        for p in paths:
            digest = hashlib.sha256(Path(p).read_bytes()).hexdigest()
            lines.append(f"{digest}  {Path(p).name}" if len(paths) > 1 else digest)
        clip = "\n".join(lines)
        short_hash = lines[0][:12] + "…"
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=list(paths),
            clipboard_text=clip,
            summary_text=f"SHA-256 copied ({short_hash})",
        )

    if action_id == "util_duplicate":
        outputs: list[str] = []
        for p in paths:
            src = Path(p)
            dst = get_safe_output_path(src, new_ext=src.suffix, suffix=" copy")
            shutil.copy2(src, dst)
            outputs.append(str(dst))
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=outputs,
            summary_text=format_saved_summary(outputs),
        )

    if action_id == "pack_zip":
        first = Path(paths[0])
        base_name = first.stem if len(paths) == 1 else f"{first.stem}_batch"
        zip_target = get_safe_output_path(first.parent / f"{base_name}.zip", new_ext=".zip")
        with zipfile.ZipFile(
            zip_target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as zf:
            used_names: set[str] = set()
            for p in paths:
                src = Path(p)
                arcname = src.name
                idx = 1
                while arcname in used_names:
                    arcname = f"{src.stem} ({idx}){src.suffix}"
                    idx += 1
                used_names.add(arcname)
                zf.write(src, arcname=arcname)
        outputs = [str(zip_target)]
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=outputs,
            summary_text=format_saved_summary(outputs),
        )

    raise ValueError(f"Unknown utility action_id: {action_id}")
