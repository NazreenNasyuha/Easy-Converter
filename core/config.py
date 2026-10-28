"""Centralized configuration constants, geometry metrics, and extension registries."""

from __future__ import annotations

from typing import Final

# Application Metadata
APP_NAME: Final[str] = "Easy Converter"
APP_ORG: Final[str] = "Easy Converter"
APP_VERSION: Final[str] = "1.1.0"
SINGLE_INSTANCE_LOCK_NAME: Final[str] = "easy_converter_instance.lock"
DEMO_FOLDER_NAME: Final[str] = "EasyConverter_Demo"

# Radial Overlay Geometry (Logical Pixels)
OVERLAY_WINDOW_SIZE: Final[int] = 380
INNER_DEADZONE_RADIUS: Final[float] = 48.0
OUTER_RING_RADIUS: Final[float] = 170.0
HOVER_EXPAND_PX: Final[float] = 8.0
WEDGE_GAP_PX: Final[float] = 4.0

# Toast Notification Geometry & Timings
TOAST_WIDTH: Final[int] = 360
TOAST_HEIGHT: Final[int] = 62
TOAST_MARGIN_PX: Final[int] = 20
TOAST_SUCCESS_DURATION_MS: Final[int] = 2500
TOAST_ERROR_DURATION_MS: Final[int] = 4000

# Input Polling & Two-Stage OLE Probe Gate Timings
POLL_INTERVAL_MS: Final[int] = 16          # 60Hz input & hover animation tick
DRAG_DISTANCE_THRESHOLD_PX: Final[float] = 15.0
OLE_PROBE_TIMEOUT_MS: Final[int] = 60      # 60ms window to confirm CF_HDROP / URLs
PROBE_OPACITY: Final[float] = 0.01         # Near-zero opacity during Stage 2 probe

# Supported File Extensions Across All 9 Categories
IMAGE_EXTS: Final[frozenset[str]] = frozenset({
    ".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif",
    ".avif", ".bmp", ".tiff", ".tif", ".ico", ".gif",
})
VIDEO_EXTS: Final[frozenset[str]] = frozenset({
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".wmv", ".m4v",
})
AUDIO_EXTS: Final[frozenset[str]] = frozenset({
    ".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".wma",
})
PDF_EXTS: Final[frozenset[str]] = frozenset({
    ".pdf",
})
DOCUMENT_EXTS: Final[frozenset[str]] = frozenset({
    ".docx", ".doc", ".txt", ".md", ".markdown", ".rtf", ".html", ".htm", ".epub",
})
SLIDES_EXTS: Final[frozenset[str]] = frozenset({
    ".pptx", ".ppt", ".odp",
})
SPREADSHEET_EXTS: Final[frozenset[str]] = frozenset({
    ".xlsx", ".xls", ".csv", ".tsv", ".json",
})
ARCHIVE_EXTS: Final[frozenset[str]] = frozenset({
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".xz", ".txz", ".7z",
})
DRAWING_EXTS: Final[frozenset[str]] = frozenset({
    ".svg", ".dxf", ".eps", ".emf", ".wmf",
})

# Standard Multi-Resolution Windows Icon Sizes
ICO_SIZES: Final[list[tuple[int, int]]] = [
    (256, 256),
    (128, 128),
    (64, 64),
    (48, 48),
    (32, 32),
    (16, 16),
]
