"""Frameless per-pixel transparent radial (pie) overlay window with OLE Drag & Drop."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from core.action_registry import (
    ModifierMode,
    SliceAction,
    format_center_badge,
    get_actions_for_files,
)
from core.config import (
    HOVER_EXPAND_PX,
    INNER_DEADZONE_RADIUS,
    OUTER_RING_RADIUS,
    OVERLAY_WINDOW_SIZE,
    POLL_INTERVAL_MS,
    PROBE_OPACITY,
    WEDGE_GAP_PX,
)
from core.ui.radial_math import (
    build_wedge_path,
    cartesian_to_polar_cw,
    hit_test_wedge,
)


class RadialOverlay(QWidget):
    """Frameless 380x380 radial pie menu supporting Windows OLE drag-and-drop and Demo Mode."""

    ole_probe_confirmed = Signal()
    action_triggered = Signal(str, str, list)  # (action_id, action_label, file_paths)
    overlay_closed = Signal()

    WINDOW_SIZE = OVERLAY_WINDOW_SIZE
    INNER_RADIUS = INNER_DEADZONE_RADIUS
    OUTER_RADIUS = OUTER_RING_RADIUS
    HOVER_EXPAND = HOVER_EXPAND_PX
    GAP_PX = WEDGE_GAP_PX

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setFixedSize(self.WINDOW_SIZE, self.WINDOW_SIZE)

        self._mode: ModifierMode = ModifierMode.SHIFT
        self._active_files: list[str] = []
        self._slices: list[SliceAction] = []
        self._center_badge: str = "DEMO"

        self._hovered_index: int = -1
        self._center_hovered: bool = False
        self._hover_progress: list[float] = []

        self._probe_pending: bool = False
        self._demo_mode: bool = False
        self._scale_factor: float = 1.0

        self._scale_anim = QPropertyAnimation(self, b"scaleFactor", self)
        self._scale_anim.setDuration(150)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutBack)

        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(POLL_INTERVAL_MS)
        self._hover_timer.timeout.connect(self._tick_hover_interpolation)

    def get_scale_factor(self) -> float:
        return self._scale_factor

    def set_scale_factor(self, value: float) -> None:
        self._scale_factor = value
        self.update()

    scaleFactor = Property(float, get_scale_factor, set_scale_factor)

    def center_on_cursor(self) -> None:
        """Position the 380x380 window centered on logical `QCursor.pos()`."""
        cursor_pos = QCursor.pos()
        self.move(
            cursor_pos.x() - self.width() // 2,
            cursor_pos.y() - self.height() // 2,
        )

    def begin_ole_probe(self, initial_mode: ModifierMode) -> None:
        """Stage 2 (Invisible OLE Probe): Show at 0.01 opacity under cursor and await `dragEnterEvent`."""
        self._probe_pending = True
        self._demo_mode = False
        self._mode = initial_mode
        self._active_files = []
        self._hovered_index = -1
        self._center_hovered = False

        self.center_on_cursor()
        self.setWindowOpacity(PROBE_OPACITY)
        self.show()
        self.raise_()

    def open_demo_mode(self, sample_files: Sequence[str] | None = None) -> None:
        """Spawn the radial menu visibly for testing/Demo Mode from the System Tray."""
        self._probe_pending = False
        self._demo_mode = True
        self._mode = ModifierMode.SHIFT
        self._active_files = [str(Path(p)) for p in sample_files] if sample_files else []

        self._rebuild_slices()
        self._hovered_index = -1
        self._center_hovered = True

        self.center_on_cursor()
        self.setWindowOpacity(1.0)
        self._scale_factor = 0.72
        self.show()
        self.raise_()
        self._scale_anim.stop()
        self._scale_anim.setStartValue(0.72)
        self._scale_anim.setEndValue(1.0)
        self._scale_anim.start()
        self._hover_timer.start()

    def close_overlay(self) -> None:
        """Immediately hide the radial menu and reset state."""
        self._probe_pending = False
        self._demo_mode = False
        self._hover_timer.stop()
        self._scale_anim.stop()
        self._hovered_index = -1
        self._center_hovered = False
        if self.isVisible():
            self.hide()
            self.overlay_closed.emit()

    def set_modifier_mode(self, mode: ModifierMode) -> None:
        """Switch between Shift (Convert), Alt (Compress), and Ctrl (Quick Actions) dynamically."""
        if self._mode is mode and self._slices:
            return
        self._mode = mode
        if self.isVisible() and not self._probe_pending:
            self._rebuild_slices()
            local_pos = self.mapFromGlobal(QCursor.pos())
            self._update_hit_test(QPointF(local_pos))
            self.update()

    def _rebuild_slices(self) -> None:
        self._slices = get_actions_for_files(self._active_files, self._mode)
        self._center_badge = format_center_badge(self._active_files)
        self._hover_progress = [0.0 for _ in self._slices]

    def _update_hit_test(self, pos: QPointF) -> None:
        """Compute polar coordinates `(r, cw_deg)` from widget center and update hovered slice."""
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        r, cw_deg = cartesian_to_polar_cw(pos.x(), pos.y(), cx, cy)
        self._center_hovered, self._hovered_index = hit_test_wedge(
            r=r,
            cw_deg=cw_deg,
            num_slices=len(self._slices),
            inner_radius=self.INNER_RADIUS,
            outer_radius=self.OUTER_RADIUS + self.HOVER_EXPAND,
        )

    def _tick_hover_interpolation(self) -> None:
        changed = False
        for i in range(len(self._hover_progress)):
            target = 1.0 if i == self._hovered_index else 0.0
            curr = self._hover_progress[i]
            if abs(target - curr) > 0.01:
                self._hover_progress[i] = curr + (target - curr) * 0.32
                changed = True
            elif curr != target:
                self._hover_progress[i] = target
                changed = True
        if changed:
            self.update()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return

        local_files: list[str] = []
        for url in mime.urls():
            if url.isLocalFile():
                local_path = url.toLocalFile()
                if os.path.isfile(local_path):
                    local_files.append(str(Path(local_path)))

        if not local_files:
            event.ignore()
            return

        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

        self._active_files = local_files
        self._rebuild_slices()
        self._update_hit_test(event.position())

        if self._probe_pending:
            self._probe_pending = False
            self.ole_probe_confirmed.emit()
            self.setWindowOpacity(1.0)
            self._scale_factor = 0.72
            self._scale_anim.stop()
            self._scale_anim.setStartValue(0.72)
            self._scale_anim.setEndValue(1.0)
            self._scale_anim.start()
            self._hover_timer.start()

        self.update()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        self._update_hit_test(event.position())
        self.update()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        event.accept()
        self._hovered_index = -1
        self._center_hovered = False
        self.update()

    def dropEvent(self, event: QDropEvent) -> None:
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

        self._update_hit_test(event.position())
        chosen_idx = self._hovered_index
        slices = list(self._slices)
        files = list(self._active_files)

        self.close_overlay()

        if 0 <= chosen_idx < len(slices) and files:
            chosen = slices[chosen_idx]
            self.action_triggered.emit(chosen.action_id, chosen.label, files)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._demo_mode:
            self._update_hit_test(event.position())
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._demo_mode and event.button() == Qt.MouseButton.LeftButton:
            self._update_hit_test(event.position())
            chosen_idx = self._hovered_index
            slices = list(self._slices)
            files = list(self._active_files)
            self.close_overlay()
            if 0 <= chosen_idx < len(slices) and files:
                chosen = slices[chosen_idx]
                self.action_triggered.emit(chosen.action_id, chosen.label, files)
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_overlay()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:
        if self._probe_pending:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 3))
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        cx = self.width() / 2.0
        cy = self.height() / 2.0

        painter.save()
        painter.translate(cx, cy)
        painter.scale(self._scale_factor, self._scale_factor)
        painter.translate(-cx, -cy)

        accent = QColor(self._mode.accent_hex)
        n = len(self._slices)

        ambient = QRadialGradient(QPointF(cx, cy), self.OUTER_RADIUS + 16.0)
        ambient_c = QColor(accent)
        ambient_c.setAlpha(38)
        ambient.setColorAt(0.25, ambient_c)
        ambient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ambient)
        painter.drawEllipse(QPointF(cx, cy), self.OUTER_RADIUS + 16.0, self.OUTER_RADIUS + 16.0)

        if n > 0:
            span = 360.0 / n
            for i, slice_action in enumerate(self._slices):
                hover_t = self._hover_progress[i] if i < len(self._hover_progress) else 0.0
                r_out = self.OUTER_RADIUS + (self.HOVER_EXPAND * hover_t)
                start_deg = i * span
                end_deg = (i + 1) * span

                wedge = build_wedge_path(
                    cx, cy, self.INNER_RADIUS, r_out, start_deg, end_deg, self.GAP_PX
                )

                base_r, base_g, base_b, base_a = 24, 24, 32, 220
                fill_r = int(base_r + (accent.red() - base_r) * (0.28 * hover_t))
                fill_g = int(base_g + (accent.green() - base_g) * (0.28 * hover_t))
                fill_b = int(base_b + (accent.blue() - base_b) * (0.28 * hover_t))
                fill_a = int(base_a + (245 - base_a) * hover_t)

                if hover_t > 0.05:
                    glow_grad = QRadialGradient(QPointF(cx, cy), r_out)
                    inner_tint = QColor(fill_r, fill_g, fill_b, fill_a)
                    outer_tint = QColor(accent)
                    outer_tint.setAlpha(int(185 * hover_t + 40))
                    glow_grad.setColorAt(self.INNER_RADIUS / r_out, inner_tint)
                    glow_grad.setColorAt(1.0, outer_tint)
                    painter.fillPath(wedge, glow_grad)
                else:
                    painter.fillPath(wedge, QColor(base_r, base_g, base_b, base_a))

                if hover_t > 0.1:
                    stroke_color = QColor(accent)
                    stroke_color.setAlpha(int(90 + 155 * hover_t))
                    pen_width = 1.2 + 0.9 * hover_t
                else:
                    stroke_color = QColor(255, 255, 255, 35)
                    pen_width = 1.1

                painter.setPen(QPen(stroke_color, pen_width))
                painter.drawPath(wedge)

                mid_deg = (start_deg + end_deg) / 2.0
                mid_rad = math.radians(mid_deg - 90.0)
                text_r = (self.INNER_RADIUS + r_out) * 0.52
                tx = cx + text_r * math.cos(mid_rad)
                ty = cy + text_r * math.sin(mid_rad)

                label_font = QFont("Segoe UI", 11 if hover_t > 0.5 else 10, QFont.Weight.Bold)
                sub_font = QFont("Segoe UI", 8, QFont.Weight.Medium)

                painter.setFont(label_font)
                painter.setPen(QColor(255, 255, 255))
                label_rect = QRectF(tx - 52.0, ty - 16.0, 104.0, 20.0)
                painter.drawText(label_rect, int(Qt.AlignmentFlag.AlignCenter), slice_action.label)

                painter.setFont(sub_font)
                sub_alpha = int(175 + 70 * hover_t)
                painter.setPen(QColor(226, 232, 240, sub_alpha))
                sub_rect = QRectF(tx - 56.0, ty + 2.0, 112.0, 16.0)
                painter.drawText(sub_rect, int(Qt.AlignmentFlag.AlignCenter), slice_action.sublabel)

        center_radius = self.INNER_RADIUS - 4.0
        center_rect = QRectF(
            cx - center_radius,
            cy - center_radius,
            center_radius * 2.0,
            center_radius * 2.0,
        )

        painter.setBrush(QColor(18, 18, 26, 238))
        if self._center_hovered:
            painter.setPen(QPen(QColor(244, 63, 94, 190), 1.8))
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 45), 1.3))
        painter.drawEllipse(center_rect)

        if self._center_hovered:
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.setPen(QColor("#FDA4AF"))
            painter.drawText(
                QRectF(cx - 40.0, cy - 10.0, 80.0, 20.0),
                int(Qt.AlignmentFlag.AlignCenter),
                "Cancel",
            )
        else:
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                QRectF(cx - 40.0, cy - 16.0, 80.0, 18.0),
                int(Qt.AlignmentFlag.AlignCenter),
                self._center_badge,
            )
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
            painter.setPen(accent)
            painter.drawText(
                QRectF(cx - 42.0, cy + 1.0, 84.0, 14.0),
                int(Qt.AlignmentFlag.AlignCenter),
                self._mode.value.upper(),
            )

        painter.restore()
