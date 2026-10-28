"""Pure geometric and polar coordinate helpers for radial menu hit-testing and rendering."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath


def cartesian_to_polar_cw(
    x: float,
    y: float,
    cx: float,
    cy: float,
) -> tuple[float, float]:
    """Convert `(x, y)` relative to `(cx, cy)` into `(r, cw_deg)` where `0°` is 12 o'clock."""
    dx = x - cx
    dy = y - cy
    r = math.hypot(dx, dy)
    cw_deg = (math.degrees(math.atan2(dy, dx)) + 90.0) % 360.0
    return r, cw_deg


def hit_test_wedge(
    r: float,
    cw_deg: float,
    num_slices: int,
    inner_radius: float,
    outer_radius: float,
) -> tuple[bool, int]:
    """Return `(center_hovered, slice_index)` for polar coordinates `(r, cw_deg)`."""
    if r < inner_radius:
        return True, -1
    if inner_radius <= r <= outer_radius and num_slices > 0:
        span = 360.0 / num_slices
        idx = int(cw_deg // span) % num_slices
        return False, idx
    return False, -1


def build_wedge_path(
    cx: float,
    cy: float,
    r_inner: float,
    r_outer: float,
    start_cw_deg: float,
    end_cw_deg: float,
    gap_px: float,
) -> QPainterPath:
    """Create an annular sector `QPainterPath` where `0°` is 12 o'clock and angles grow clockwise."""
    inner_half_gap = math.degrees((gap_px / 2.0) / max(r_inner, 1.0))
    outer_half_gap = math.degrees((gap_px / 2.0) / max(r_outer, 1.0))

    s_in = start_cw_deg + inner_half_gap
    e_in = end_cw_deg - inner_half_gap
    s_out = start_cw_deg + outer_half_gap
    e_out = end_cw_deg - outer_half_gap

    if e_in <= s_in or e_out <= s_out:
        return QPainterPath()

    qt_start_out = 90.0 - s_out
    qt_sweep_out = -(e_out - s_out)

    qt_end_in = 90.0 - e_in
    qt_sweep_in = e_in - s_in

    outer_rect = QRectF(cx - r_outer, cy - r_outer, r_outer * 2.0, r_outer * 2.0)
    inner_rect = QRectF(cx - r_inner, cy - r_inner, r_inner * 2.0, r_inner * 2.0)

    s_out_rad = math.radians(s_out - 90.0)
    p_start_outer = QPointF(
        cx + r_outer * math.cos(s_out_rad),
        cy + r_outer * math.sin(s_out_rad),
    )

    path = QPainterPath()
    path.moveTo(p_start_outer)
    path.arcTo(outer_rect, qt_start_out, qt_sweep_out)
    path.arcTo(inner_rect, qt_end_in, qt_sweep_in)
    path.closeSubpath()
    return path
