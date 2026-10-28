"""Conversion dispatcher routing action IDs to all 9 specialized domain handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from core.converters.archive_ops import ARCHIVE_ACTION_IDS, run_archive_action
from core.converters.document_ops import DOCUMENT_ACTION_IDS, run_document_action
from core.converters.drawing_ops import DRAWING_ACTION_IDS, run_drawing_action
from core.converters.image_ops import IMAGE_ACTION_IDS, run_image_action
from core.converters.media_ops import MEDIA_ACTION_IDS, resolve_ffmpeg_exe, run_media_action
from core.converters.path_utils import format_saved_summary, get_safe_output_path
from core.converters.pdf_ops import PDF_ACTION_IDS, merge_files_to_pdf, run_pdf_action
from core.converters.slides_ops import SLIDES_ACTION_IDS, run_slides_action
from core.converters.spreadsheet_ops import SPREADSHEET_ACTION_IDS, run_spreadsheet_action
from core.converters.utility_ops import UTILITY_ACTION_IDS, run_utility_action
from core.models import ConversionResult

__all__ = [
    "ConversionResult",
    "execute_action",
    "format_saved_summary",
    "get_safe_output_path",
    "resolve_ffmpeg_exe",
]


def _run_result_wrapped_domain(
    action_id: str,
    action_label: str,
    paths: list[str],
    runner,
) -> ConversionResult:
    """Run a domain handler that returns `ConversionResult` across one or more input files."""
    if len(paths) == 1:
        return runner(action_id, action_label, Path(paths[0]))

    all_outputs: list[str] = []
    clip_parts: list[str] = []
    last_summary = ""
    for p in paths:
        res = runner(action_id, action_label, Path(p))
        if not res.success:
            return res
        all_outputs.extend(res.output_paths)
        if res.clipboard_text:
            clip_parts.append(res.clipboard_text)
        last_summary = res.summary_text

    return ConversionResult(
        success=True,
        action_id=action_id,
        action_label=action_label,
        output_paths=all_outputs,
        clipboard_text="\n".join(clip_parts) if clip_parts else None,
        summary_text=format_saved_summary(all_outputs) if not clip_parts else last_summary,
    )


def execute_action(
    action_id: str,
    action_label: str,
    file_paths: Sequence[str],
) -> ConversionResult:
    """Dispatch `action_id` across `file_paths` and return a structured `ConversionResult`."""
    paths = [str(Path(p)) for p in file_paths if p]
    if not paths:
        return ConversionResult(
            success=False,
            action_id=action_id,
            action_label=action_label,
            error_message="No input files provided.",
        )

    if action_id in UTILITY_ACTION_IDS:
        return run_utility_action(action_id, action_label, paths)

    if action_id == "batch_merge_pdf":
        out_pdf = merge_files_to_pdf(paths)
        outputs = [str(out_pdf)]
        return ConversionResult(
            success=True,
            action_id=action_id,
            action_label=action_label,
            output_paths=outputs,
            summary_text=format_saved_summary(outputs),
        )

    if action_id in DOCUMENT_ACTION_IDS:
        return _run_result_wrapped_domain(action_id, action_label, paths, run_document_action)

    if action_id in SLIDES_ACTION_IDS:
        return _run_result_wrapped_domain(action_id, action_label, paths, run_slides_action)

    if action_id in SPREADSHEET_ACTION_IDS:
        return _run_result_wrapped_domain(action_id, action_label, paths, run_spreadsheet_action)

    if action_id in ARCHIVE_ACTION_IDS:
        return _run_result_wrapped_domain(action_id, action_label, paths, run_archive_action)

    if action_id in DRAWING_ACTION_IDS:
        return _run_result_wrapped_domain(action_id, action_label, paths, run_drawing_action)

    outputs: list[str] = []
    for p in paths:
        src = Path(p)
        if action_id in IMAGE_ACTION_IDS:
            produced = run_image_action(action_id, src)
        elif action_id in PDF_ACTION_IDS:
            produced = run_pdf_action(action_id, src)
        elif action_id in MEDIA_ACTION_IDS:
            produced = run_media_action(action_id, src)
        else:
            raise ValueError(f"Unsupported action_id: {action_id}")
        outputs.extend(str(out) for out in produced)

    return ConversionResult(
        success=True,
        action_id=action_id,
        action_label=action_label,
        output_paths=outputs,
        summary_text=format_saved_summary(outputs),
    )
