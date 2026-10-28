"""Vector QPainter icon generator for Easy Converter window and system tray icons."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)


def create_app_icon(size: int = 64) -> QIcon:
    """Render a crisp vector radial wheel icon in memory for the Windows 11 system tray."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    cx = size / 2.0
    cy = size / 2.0 + 2.0
    r = size * 0.38

    grad = QRadialGradient(QPointF(cx - r * 0.25, cy - r * 0.25), r * 1.35)
    grad.setColorAt(0.0, QColor("#FFB347"))
    grad.setColorAt(0.65, QColor("#FF8C42"))
    grad.setColorAt(1.0, QColor("#E05A19"))

    painter.setPen(QPen(QColor(255, 255, 255, 60), 1.5))
    painter.setBrush(grad)
    painter.drawEllipse(QPointF(cx, cy), r, r)

    seg_pen = QPen(QColor(255, 255, 255, 70), 1.2)
    painter.setPen(seg_pen)
    painter.drawEllipse(QPointF(cx, cy), r * 0.28, r * 0.28)

    leaf = QPainterPath()
    leaf.moveTo(cx, cy - r + 1.0)
    leaf.quadTo(cx + r * 0.45, cy - r * 1.45, cx + r * 0.65, cy - r * 0.95)
    leaf.quadTo(cx + r * 0.25, cy - r * 0.75, cx, cy - r + 1.0)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#22C55E"))
    painter.drawPath(leaf)

    painter.end()
    return QIcon(pixmap)
