"""60Hz Win32 `GetAsyncKeyState` input monitor and Two-Stage OLE Probe Gate state machine."""

from __future__ import annotations

import math

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtGui import QCursor

from core.config import (
    DRAG_DISTANCE_THRESHOLD_PX,
    OLE_PROBE_TIMEOUT_MS,
    POLL_INTERVAL_MS,
)
from core.models import ModifierMode, WatcherState
from core.radial_overlay import RadialOverlay
from core.win32_input import (
    VK_ESCAPE,
    detect_modifier_mode,
    is_primary_mouse_down,
    is_vk_down,
)


class DragWatcher(QObject):
    """Polls `GetAsyncKeyState` at 60Hz (16ms) and coordinates the 60ms OLE Probe Gate."""

    DRAG_THRESHOLD_PX = DRAG_DISTANCE_THRESHOLD_PX
    PROBE_TIMEOUT_MS = OLE_PROBE_TIMEOUT_MS

    def __init__(self, overlay: RadialOverlay, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.overlay = overlay
        self.enabled: bool = True

        self._state: WatcherState = WatcherState.IDLE
        self._pos_start: QPoint = QPoint(0, 0)
        self._last_mode: ModifierMode = ModifierMode.SHIFT

        self.overlay.ole_probe_confirmed.connect(self._on_ole_probe_confirmed)
        self.overlay.overlay_closed.connect(self._on_overlay_closed)

        self._probe_timer = QTimer(self)
        self._probe_timer.setSingleShot(True)
        self._probe_timer.setInterval(self.PROBE_TIMEOUT_MS)
        self._probe_timer.timeout.connect(self._on_probe_timeout)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_tick)
        self._poll_timer.start()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or pause the Shift-Drag listener."""
        self.enabled = enabled
        if not enabled:
            self._probe_timer.stop()
            self._state = WatcherState.IDLE
            if self.overlay.isVisible() and not self.overlay._demo_mode:
                self.overlay.close_overlay()

    def _on_ole_probe_confirmed(self) -> None:
        """Transition to CONFIRMED state when `dragEnterEvent` validates local files within 60ms."""
        self._probe_timer.stop()
        self._state = WatcherState.CONFIRMED

    def _on_probe_timeout(self) -> None:
        """Abort and suppress re-probing if 60ms elapses without `dragEnterEvent`."""
        if self._state is WatcherState.PROBING:
            self.overlay.close_overlay()
            self._state = WatcherState.SUPPRESSED

    def _on_overlay_closed(self) -> None:
        self._probe_timer.stop()
        if is_primary_mouse_down():
            self._state = WatcherState.SUPPRESSED
        else:
            self._state = WatcherState.IDLE

    def _poll_tick(self) -> None:
        if not self.enabled:
            return

        if self.overlay.isVisible() and self.overlay._demo_mode:
            if is_vk_down(VK_ESCAPE):
                self.overlay.close_overlay()
                return
            mod = detect_modifier_mode()
            if mod is not None and mod is not self._last_mode:
                self._last_mode = mod
                self.overlay.set_modifier_mode(mod)
            return

        lbutton_down = is_primary_mouse_down()

        if not lbutton_down:
            if self._state in (WatcherState.PROBING, WatcherState.CONFIRMED):
                self._probe_timer.stop()
                self.overlay.close_overlay()
            self._state = WatcherState.IDLE
            return

        if self._state is WatcherState.IDLE:
            self._pos_start = QCursor.pos()
            self._state = WatcherState.DRAGGING
            return

        if self._state is WatcherState.DRAGGING:
            cur_pos = QCursor.pos()
            dist = math.hypot(
                cur_pos.x() - self._pos_start.x(),
                cur_pos.y() - self._pos_start.y(),
            )
            if dist > self.DRAG_THRESHOLD_PX:
                mod = detect_modifier_mode()
                if mod is not None:
                    self._last_mode = mod
                    self._state = WatcherState.PROBING
                    self.overlay.begin_ole_probe(mod)
                    self._probe_timer.start()
            return

        if self._state is WatcherState.CONFIRMED:
            if is_vk_down(VK_ESCAPE):
                self.overlay.close_overlay()
                self._state = WatcherState.SUPPRESSED
                return

            mod = detect_modifier_mode()
            if mod is not None and mod is not self._last_mode:
                self._last_mode = mod
                self.overlay.set_modifier_mode(mod)
