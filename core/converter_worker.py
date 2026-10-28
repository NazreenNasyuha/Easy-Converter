"""Background QRunnable conversion workers delegating to the `core.converters` package."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from core.converters import (
    ConversionResult,
    execute_action,
    get_safe_output_path,
    resolve_ffmpeg_exe,
)

__all__ = [
    "ConversionResult",
    "ConversionWorker",
    "WorkerSignals",
    "execute_action",
    "get_safe_output_path",
    "resolve_ffmpeg_exe",
]


class WorkerSignals(QObject):
    """Qt signals emitted by `ConversionWorker` from a `QThreadPool` worker thread."""

    started_job = Signal(str)     # Progress message, e.g. "Converting photo.png → WEBP..."
    finished_job = Signal(object) # Emits ConversionResult


class ConversionWorker(QRunnable):
    """Asynchronous `QRunnable` executing file conversions off the Qt GUI thread."""

    def __init__(
        self,
        action_id: str,
        action_label: str,
        file_paths: Sequence[str],
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self.action_id = action_id
        self.action_label = action_label
        self.file_paths = list(file_paths)
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        first_name = Path(self.file_paths[0]).name if self.file_paths else "file"
        source_desc = (
            f"{len(self.file_paths)} files" if len(self.file_paths) > 1 else first_name
        )

        self.signals.started_job.emit(f"Converting {source_desc} → {self.action_label}...")
        try:
            result = execute_action(self.action_id, self.action_label, self.file_paths)
        except Exception as exc:
            traceback.print_exc()
            result = ConversionResult(
                success=False,
                action_id=self.action_id,
                action_label=self.action_label,
                error_message=str(exc),
            )
        self.signals.finished_job.emit(result)
