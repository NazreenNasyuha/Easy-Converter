"""Interactive 'Crop & Edit' Image Studio dialog for Easy Converter."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.converters.image_ops import remove_image_background
from core.converters.path_utils import get_safe_output_path


def pil_to_qpixmap(img: Image.Image) -> QPixmap:
    """Convert a PIL Image into a Qt `QPixmap`."""
    rgba = img.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


class _CropCanvas(QWidget):
    """Interactive canvas displaying the image preview and draggable crop rectangle."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(540, 380)
        self._pixmap: QPixmap | None = None
        self._img_rect = QRectF()
        self._crop_norm = QRectF(0.0, 0.0, 1.0, 1.0)  # Normalized [0..1] crop box
        self._drag_start: QPointF | None = None
        self._aspect_ratio: float | None = None

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def reset_crop(self) -> None:
        self._crop_norm = QRectF(0.0, 0.0, 1.0, 1.0)
        self.update()

    def set_aspect_preset(self, preset: str, img_w: int, img_h: int) -> None:
        if preset == "Full (No Crop)":
            self._aspect_ratio = None
            self._crop_norm = QRectF(0.0, 0.0, 1.0, 1.0)
            self.update()
            return
        ratios = {
            "Free Crop": None,
            "1:1 Square": 1.0,
            "16:9 Widescreen": 16.0 / 9.0,
            "4:3 Standard": 4.0 / 3.0,
            "9:16 Vertical": 9.0 / 16.0,
        }
        ratio = ratios.get(preset)
        self._aspect_ratio = ratio
        if ratio is None or img_w <= 0 or img_h <= 0:
            self.update()
            return

        # Compute centered normalized crop box matching target aspect ratio
        current_ratio = img_w / img_h
        if current_ratio > ratio:
            norm_w = ratio / current_ratio
            norm_h = 1.0
        else:
            norm_w = 1.0
            norm_h = current_ratio / ratio

        self._crop_norm = QRectF(
            (1.0 - norm_w) / 2.0,
            (1.0 - norm_h) / 2.0,
            norm_w,
            norm_h,
        )
        self.update()

    def get_crop_norm(self) -> tuple[float, float, float, float]:
        r = self._crop_norm.normalized()
        x1 = max(0.0, min(1.0, r.left()))
        y1 = max(0.0, min(1.0, r.top()))
        x2 = max(0.0, min(1.0, r.right()))
        y2 = max(0.0, min(1.0, r.bottom()))
        if (x2 - x1) < 0.03 or (y2 - y1) < 0.03:
            return (0.0, 0.0, 1.0, 1.0)
        return (x1, y1, x2, y2)

    def _widget_to_norm(self, pt: QPointF) -> QPointF:
        if self._img_rect.width() <= 1 or self._img_rect.height() <= 1:
            return QPointF(0.0, 0.0)
        nx = (pt.x() - self._img_rect.left()) / self._img_rect.width()
        ny = (pt.y() - self._img_rect.top()) / self._img_rect.height()
        return QPointF(max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny)))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = self._widget_to_norm(event.position())
            self._crop_norm = QRectF(self._drag_start, self._drag_start)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None:
            cur = self._widget_to_norm(event.position())
            rect = QRectF(self._drag_start, cur).normalized()
            self._crop_norm = rect
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start is not None:
            cur = self._widget_to_norm(event.position())
            rect = QRectF(self._drag_start, cur).normalized()
            if rect.width() < 0.03 or rect.height() < 0.03:
                self._crop_norm = QRectF(0.0, 0.0, 1.0, 1.0)
            else:
                self._crop_norm = rect
            self._drag_start = None
            self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(15, 17, 24))

        if self._pixmap is None or self._pixmap.isNull():
            return

        avail_w = self.width() - 24.0
        avail_h = self.height() - 24.0
        pw = float(self._pixmap.width())
        ph = float(self._pixmap.height())
        scale = min(avail_w / max(pw, 1.0), avail_h / max(ph, 1.0))
        draw_w = pw * scale
        draw_h = ph * scale
        dx = (self.width() - draw_w) / 2.0
        dy = (self.height() - draw_h) / 2.0
        self._img_rect = QRectF(dx, dy, draw_w, draw_h)

        painter.drawPixmap(self._img_rect.toRect(), self._pixmap)

        # Draw crop overlay
        x1, y1, x2, y2 = self.get_crop_norm()
        crop_px = QRectF(
            dx + x1 * draw_w,
            dy + y1 * draw_h,
            (x2 - x1) * draw_w,
            (y2 - y1) * draw_h,
        )

        # Dim outside crop area
        dim_color = QColor(0, 0, 0, 145)
        painter.fillRect(QRectF(dx, dy, draw_w, crop_px.top() - dy), dim_color)
        painter.fillRect(QRectF(dx, crop_px.bottom(), draw_w, dy + draw_h - crop_px.bottom()), dim_color)
        painter.fillRect(QRectF(dx, crop_px.top(), crop_px.left() - dx, crop_px.height()), dim_color)
        painter.fillRect(
            QRectF(crop_px.right(), crop_px.top(), dx + draw_w - crop_px.right(), crop_px.height()),
            dim_color,
        )

        # Crop border & rule-of-thirds grid
        painter.setPen(QPen(QColor("#38BDF8"), 2.0))
        painter.drawRect(crop_px)

        grid_pen = QPen(QColor(255, 255, 255, 70), 1.0, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        for i in (1, 2):
            gx = crop_px.left() + (crop_px.width() * i / 3.0)
            gy = crop_px.top() + (crop_px.height() * i / 3.0)
            painter.drawLine(QPointF(gx, crop_px.top()), QPointF(gx, crop_px.bottom()))
            painter.drawLine(QPointF(crop_px.left(), gy), QPointF(crop_px.right(), gy))


class ImageEditorDialog(QDialog):
    """Dark-glass Quick Image Studio for interactive cropping, rotation, background removal, and tuning."""

    image_saved = Signal(str)  # Emits output file path when saved

    def __init__(self, source_path: str | Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source_path = Path(source_path)
        self.setWindowTitle(f"Easy Converter Image Studio — {self.source_path.name}")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(760, 560)

        with Image.open(self.source_path) as raw:
            self._base_img = ImageOps.exif_transpose(raw).convert("RGBA")

        self._working_img = self._base_img.copy()
        self._rotation_deg = 0
        self._flip_h = False
        self._flip_v = False
        self._grayscale = False
        self._bg_removed = False

        self._setup_ui()
        self._refresh_preview()

    def _setup_ui(self) -> None:
        self.setStyleSheet(
            """
            QDialog { background-color: #14161f; color: #f8fafc; font-family: 'Segoe UI'; }
            QLabel { color: #cbd5e1; font-size: 12px; font-weight: 600; }
            QPushButton {
                background-color: #1e293b; color: #f8fafc; border: 1px solid #334155;
                border-radius: 6px; padding: 6px 12px; font-weight: 600;
            }
            QPushButton:hover { background-color: #334155; border-color: #38bdf8; }
            QPushButton#saveBtn { background-color: #ff8c42; color: #0f172a; border: none; font-weight: 700; }
            QPushButton#saveBtn:hover { background-color: #ffa05c; }
            QComboBox {
                background-color: #1e293b; color: #f8fafc; border: 1px solid #334155;
                border-radius: 6px; padding: 5px 10px;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # Top toolbar: Aspect preset + Transform buttons
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Crop Aspect:"))

        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems([
            "Free Crop",
            "1:1 Square",
            "16:9 Widescreen",
            "4:3 Standard",
            "9:16 Vertical",
            "Full (No Crop)",
        ])
        self.aspect_combo.currentTextChanged.connect(self._on_aspect_changed)
        top_bar.addWidget(self.aspect_combo)

        btn_rot = QPushButton("Rotate 90°")
        btn_rot.clicked.connect(self._on_rotate)
        top_bar.addWidget(btn_rot)

        btn_fh = QPushButton("Flip H")
        btn_fh.clicked.connect(self._on_flip_h)
        top_bar.addWidget(btn_fh)

        btn_fv = QPushButton("Flip V")
        btn_fv.clicked.connect(self._on_flip_v)
        top_bar.addWidget(btn_fv)

        btn_bg = QPushButton("Remove BG")
        btn_bg.clicked.connect(self._on_toggle_remove_bg)
        top_bar.addWidget(btn_bg)

        btn_gray = QPushButton("Grayscale")
        btn_gray.clicked.connect(self._on_toggle_gray)
        top_bar.addWidget(btn_gray)

        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self._on_reset)
        top_bar.addWidget(btn_reset)

        root.addLayout(top_bar)

        # Interactive crop canvas
        self.canvas = _CropCanvas(self)
        root.addWidget(self.canvas, stretch=1)

        # Sliders bar: Brightness, Contrast, Sharpness
        sliders_bar = QHBoxLayout()
        self.bright_slider = self._add_slider(sliders_bar, "Brightness", 50, 150, 100)
        self.contrast_slider = self._add_slider(sliders_bar, "Contrast", 50, 150, 100)
        self.sharp_slider = self._add_slider(sliders_bar, "Sharpness", 50, 200, 100)
        root.addLayout(sliders_bar)

        # Bottom action buttons
        bottom_bar = QHBoxLayout()
        hint = QLabel("Drag on image to draw crop box  •  Saves to a new non-overwriting file")
        hint.setStyleSheet("color: #94a3b8; font-weight: 400;")
        bottom_bar.addWidget(hint)
        bottom_bar.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        bottom_bar.addWidget(cancel_btn)

        save_btn = QPushButton("Save Edited Copy")
        save_btn.setObjectName("saveBtn")
        save_btn.clicked.connect(self._on_save)
        bottom_bar.addWidget(save_btn)

        root.addLayout(bottom_bar)

    def _add_slider(
        self,
        layout: QHBoxLayout,
        label_text: str,
        min_v: int,
        max_v: int,
        default_v: int,
    ) -> QSlider:
        layout.addWidget(QLabel(f"{label_text}:"))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(default_v)
        slider.valueChanged.connect(self._refresh_preview)
        layout.addWidget(slider)
        return slider

    def _build_transformed_image(self, apply_crop: bool = False) -> Image.Image:
        img = self._base_img.copy()
        if self._bg_removed:
            img = remove_image_background(img)
        if self._rotation_deg:
            img = img.rotate(-self._rotation_deg, expand=True)
        if self._flip_h:
            img = ImageOps.mirror(img)
        if self._flip_v:
            img = ImageOps.flip(img)

        b_factor = self.bright_slider.value() / 100.0
        c_factor = self.contrast_slider.value() / 100.0
        s_factor = self.sharp_slider.value() / 100.0

        if abs(b_factor - 1.0) > 0.01:
            img = ImageEnhance.Brightness(img).enhance(b_factor)
        if abs(c_factor - 1.0) > 0.01:
            img = ImageEnhance.Contrast(img).enhance(c_factor)
        if abs(s_factor - 1.0) > 0.01:
            img = ImageEnhance.Sharpness(img).enhance(s_factor)
        if self._grayscale:
            alpha = img.getchannel("A")
            gray = ImageOps.grayscale(img.convert("RGB")).convert("RGBA")
            gray.putalpha(alpha)
            img = gray

        if apply_crop:
            x1, y1, x2, y2 = self.canvas.get_crop_norm()
            w, h = img.size
            box = (
                int(round(x1 * w)),
                int(round(y1 * h)),
                max(int(round(x1 * w)) + 1, int(round(x2 * w))),
                max(int(round(y1 * h)) + 1, int(round(y2 * h))),
            )
            img = img.crop(box)

        return img

    def _refresh_preview(self) -> None:
        self._working_img = self._build_transformed_image(apply_crop=False)
        self.canvas.set_pixmap(pil_to_qpixmap(self._working_img))

    def _on_aspect_changed(self, text: str) -> None:
        w, h = self._working_img.size
        self.canvas.set_aspect_preset(text, w, h)

    def _on_rotate(self) -> None:
        self._rotation_deg = (self._rotation_deg + 90) % 360
        self._refresh_preview()

    def _on_flip_h(self) -> None:
        self._flip_h = not self._flip_h
        self._refresh_preview()

    def _on_flip_v(self) -> None:
        self._flip_v = not self._flip_v
        self._refresh_preview()

    def _on_toggle_remove_bg(self) -> None:
        self._bg_removed = not self._bg_removed
        self._refresh_preview()

    def _on_toggle_gray(self) -> None:
        self._grayscale = not self._grayscale
        self._refresh_preview()

    def _on_reset(self) -> None:
        self._rotation_deg = 0
        self._flip_h = False
        self._flip_v = False
        self._grayscale = False
        self._bg_removed = False
        self.bright_slider.setValue(100)
        self.contrast_slider.setValue(100)
        self.sharp_slider.setValue(100)
        self.canvas.reset_crop()
        self._refresh_preview()

    def _on_save(self) -> None:
        final_img = self._build_transformed_image(apply_crop=True)
        out_ext = ".png" if self._bg_removed or self.source_path.suffix.lower() in (".heic", ".heif") else self.source_path.suffix
        dst = get_safe_output_path(self.source_path, new_ext=out_ext, suffix="_edited")
        if dst.suffix.lower() in (".jpg", ".jpeg"):
            from core.converters.image_ops import flatten_to_rgb

            flatten_to_rgb(final_img).save(dst, format="JPEG", quality=92, optimize=True)
        else:
            final_img.save(dst)
        self.image_saved.emit(str(dst))
        self.accept()
