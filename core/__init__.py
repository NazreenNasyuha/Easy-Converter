"""Easy Converter core package exposing configuration, models, registry, workers, and UI."""

from core.action_registry import (
    format_center_badge,
    get_actions_for_files,
    get_ctrl_actions,
    normalize_ext,
)
from core.config import APP_NAME, APP_VERSION
from core.converter_worker import ConversionWorker, WorkerSignals, execute_action, get_safe_output_path
from core.models import ConversionResult, ModifierMode, SliceAction, WatcherState

__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "ConversionResult",
    "ConversionWorker",
    "ModifierMode",
    "SliceAction",
    "WatcherState",
    "WorkerSignals",
    "execute_action",
    "format_center_badge",
    "get_actions_for_files",
    "get_ctrl_actions",
    "get_safe_output_path",
    "normalize_ext",
]
