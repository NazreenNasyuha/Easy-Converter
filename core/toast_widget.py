"""Non-blocking floating pill toast notification with 'Reveal in Explorer' click action."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
     QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QWidget


class ToastWidget(QWidget):
    """Compact floating status pill anchored at the bottom-right of the primary screen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(360, 62)

        self._status: str = "progress"  # "progress" | "success" | "error"
        self._title_text: str = ""
        self._sub_text: str = ""
        self._target_path: str | None = None
        self._spin_angle: int = 0

        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(24)
        self._spin_timer.timeout.connect(self._on_spin_tick)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.fade_out)

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(180)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.finished.connect(self._on_fade_finished)
        self._fading_out = False

    def _reposition_bottom_right(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        x = avail.right() - self.width() - 20
        y = avail.bottom() - self.height() - 20
        self.move(x, y)

    def show_progress(self, message: str) -> None:
        """Display an active conversion progress state."""
        self._dismiss_timer.stop()
        self._fading_out = False
        self._status = "progress"
        self._title_text = message
        self._sub_text = "Running in background…"
        self._target_path = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._reposition_bottom_right()
        self._spin_timer.start()
        self._show_animated()
        self.update()

    def show_success(
        self,
        message: str,
        output_path: str | None = None,
        sub_text: str | None = None,
        duration_ms: int = 2500,
    ) -> None:
        """Transition to green checkmark state and auto-dismiss after 2.5s."""
        self._spin_timer.stop()
        self._dismiss_timer.stop()
        self._fading_out = False
        self._status = "success"
        self._title_text = message
        self._target_path = output_path
        if sub_text is not None:
            self._sub_text = sub_text
        elif output_path and os.path.exists(output_path):
            self._sub_text = "Click to reveal in File Explorer"
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._sub_text = "Completed"
            self.setCursor(Qt.CursorShape.ArrowCursor)

        self._reposition_bottom_right()
        self._show_animated()
        self.update()
        self._dismiss_timer.start(duration_ms)

    def show_error(self, error_msg: str, duration_ms: int = 4000) -> None:
        """Display an error toast pill."""
        self._spin_timer.stop()
        self._dismiss_timer.stop()
        self._fading_out = False
        self._status = "error"
        self._title_text = "Conversion Failed"
        self._sub_text = error_msg[:58] + ("…" if len(error_msg) > 58 else "")
        self._target_path = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._reposition_bottom_right()
        self._show_animated()
        self.update()
        self._dismiss_timer.start(duration_ms)

    def _show_animated(self) -> None:
        self._fade_anim.stop()
        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.show()
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def fade_out(self) -> None:
        if not self.isVisible():
            return
        self._fading_out = True
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _on_fade_finished(self) -> None:
        if self._fading_out:
            self._spin_timer.stop()
            self.hide()
            self._fading_out = False

    def _on_spin_tick(self) -> None:
        self._spin_angle = (self._spin_angle + 18) % 360
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._target_path and os.path.exists(self._target_path):
                norm_path = str(Path(self._target_path).resolve())
                subprocess.Popen(["explorer.exe", f'/select,"{norm_path}"'])
            self.fade_out()
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = QRectF(2.0, 2.0, self.width() - 4.0, self.height() - 4.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 16.0, 16.0)

        # Dark glass pill background
        painter.fillPath(path, QColor(22, 22, 30, 238))

        # Subtle border stroke
        if self._status == "success":
            border_color = QColor(34, 197, 94, 120)
        elif self._status == "error":
            border_color = QColor(239, 68, 68, 130)
        else:
            border_color = QColor(255, 140, 66, 110)

        pen = QPen(border_color, 1.4)
        painter.setPen(pen)
        painter.drawPath(path)

        # Status icon on the left
        icon_center = QPointF(30.0, self.height() / 2.0)
        icon_radius = 12.0

        if self._status == "progress":
            # Spinning tangerine arc
            arc_rect = QRectF(
                icon_center.x() - icon_radius,
                icon_center.y() - icon_radius,
                icon_radius * 2,
                icon_radius * 2,
            )
            track_pen = QPen(QColor(255, 255, 255, 35), 2.6)
            painter.setPen(track_pen)
            painter.drawEllipse(arc_rect)

            spin_pen = QPen(QColor("#FF8C42"), 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(spin_pen)
            painter.drawArc(arc_rect, -self._spin_angle * 16, 110 * 16)

        elif self._status == "success":
            # Green circle + white checkmark
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#22C55E"))
            painter.drawEllipse(icon_center, icon_radius, icon_radius)

            check_pen = QPen(QColor(255, 255, 255), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(check_pen)
            cx, cy = icon_center.x(), icon_center.y()
            painter.drawLine(QPointF(cx - 5.0, cy + 0.5), QPointF(cx - 1.2, cy + 4.2))
            painter.drawLine(QPointF(cx - 1.2, cy + 4.2), QPointF(cx + 5.5, cy - 3.8))

        else:
            # Red error badge
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#EF4444"))
            painter.drawEllipse(icon_center, icon_radius, icon_radius)

            x_pen = QPen(QColor(255, 255, 255), 2.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(x_pen)
            cx, cy = icon_center.x(), icon_center.y()
            painter.drawLine(QPointF(cx - 4.0, cy - 4.0), QPointF(cx + 4.0, cy + 4.0))
            painter.drawLine(QPointF(cx + 4.0, cy - 4.0), QPointF(cx - 4.0, cy + 4.0))

        # Typography
        title_font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        sub_font = QFont("Segoe UI", 8, QFont.Weight.Normal)

        text_left = 54.0
        text_width = self.width() - text_left - 14.0

        painter.setFont(title_font)
        painter.setPen(QColor(248, 250, 252))
        metrics = painter.fontMetrics()
        elided_title = metrics.elidedText(self._title_text, Qt.TextElideMode.ElideMiddle, int(text_width))
        painter.drawText(
            QRectF(text_left, 11.0, text_width, 20.0),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elided_title,
        )

        painter.setFont(sub_font)
        painter.setPen(QColor(168, 178, 195))
        sub_metrics = painter.fontMetrics()
        elided_sub = sub_metrics.elidedText(self._sub_text, Qt.TextElideMode.ElideRight, int(text_width))
        painter.drawText(
            QRectF(text_left, 31.0, text_width, 18.0),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elided_sub,
        )
