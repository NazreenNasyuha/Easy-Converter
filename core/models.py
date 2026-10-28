"""Domain models and enums shared across Easy Converter subsystems."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ModifierMode(Enum):
    """Active modifier key mode controlling radial slices and theme accents."""

    SHIFT = "shift"  # Format Conversion (Default)
    ALT = "alt"      # Compression & Sizing Tools
    CTRL = "ctrl"    # Quick File Utilities

    @property
    def title(self) -> str:
        if self is ModifierMode.SHIFT:
            return "Convert Format"
        if self is ModifierMode.ALT:
            return "Compress & Size"
        return "Quick Actions"

    @property
    def accent_hex(self) -> str:
        if self is ModifierMode.SHIFT:
            return "#FF8C42"  # Orange
        if self is ModifierMode.ALT:
            return "#38BDF8"  # Sky Blue
        return "#A855F7"      # Purple


class WatcherState(Enum):
    """State machine states for the Two-Stage OLE Probe Gate."""

    IDLE = "idle"
    DRAGGING = "dragging"
    PROBING = "probing"
    CONFIRMED = "confirmed"
    SUPPRESSED = "suppressed"


@dataclass(frozen=True)
class SliceAction:
    """Immutable descriptor for a single radial menu wedge action."""

    action_id: str
    label: str
    sublabel: str
    target_ext: str | None = None
    mode: ModifierMode = ModifierMode.SHIFT


@dataclass
class ConversionResult:
    """Result payload emitted when a conversion or utility worker completes."""

    success: bool
    action_id: str
    action_label: str
    output_paths: list[str] = field(default_factory=list)
    clipboard_text: str | None = None
    summary_text: str = ""
    error_message: str = ""
