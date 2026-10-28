"""System Tray controller coordinating RadialOverlay, DragWatcher, QThreadPool, and ToastWidget."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QThreadPool
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.config import APP_NAME, DEMO_FOLDER_NAME
from core.converter_worker import ConversionResult, ConversionWorker
from core.drag_watcher import DragWatcher
from core.radial_overlay import RadialOverlay
from core.toast_widget import ToastWidget
from core.ui.icon_factory import create_app_icon
from core.ui.image_editor_dialog import ImageEditorDialog


class EasyConverterController(QObject):
    """Application controller managing the system tray, drag watcher, Image Studio, and worker pool."""

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.thread_pool = QThreadPool.globalInstance()
        self._active_workers: list[ConversionWorker] = []
        self._editor_dialog: ImageEditorDialog | None = None

        self.icon = create_app_icon(64)
        self.app.setWindowIcon(self.icon)

        self.overlay = RadialOverlay()
        self.toast = ToastWidget()
        self.watcher = DragWatcher(self.overlay, self)

        self.overlay.action_triggered.connect(self.start_conversion)

        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setToolTip(f"{APP_NAME} — Shift-Drag Radial File Converter")
        self._build_tray_menu()
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _build_tray_menu(self) -> None:
        menu = QMenu()

        self.toggle_action = QAction("Enable / Pause Shift-Drag Listener", menu)
        self.toggle_action.setCheckable(True)
        self.toggle_action.setChecked(True)
        self.toggle_action.toggled.connect(self._on_toggle_listener)
        menu.addAction(self.toggle_action)

        demo_action = QAction("Test Radial Overlay (Demo Mode)", menu)
        demo_action.triggered.connect(self.launch_demo_mode)
        menu.addAction(demo_action)

        menu.addSeparator()

        quit_action = QAction(f"Quit {APP_NAME}", menu)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)

    def _on_toggle_listener(self, checked: bool) -> None:
        self.watcher.set_enabled(checked)
        state_str = "Enabled" if checked else "Paused"
        self.tray.setToolTip(f"{APP_NAME} — Listener {state_str}")
        self.toast.show_success(
            f"Shift-Drag Listener {state_str}",
            sub_text="Hold Left-Click drag + Shift / Alt / Ctrl on any file",
            duration_ms=1800,
        )

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.launch_demo_mode()

    def launch_demo_mode(self) -> None:
        """Create a sample demo image in a temp folder and open the radial wheel under the cursor."""
        demo_dir = Path(tempfile.gettempdir()) / DEMO_FOLDER_NAME
        demo_dir.mkdir(parents=True, exist_ok=True)
        demo_img_path = demo_dir / "demo_sample.png"
        if not demo_img_path.exists():
            from PIL import Image, ImageDraw

            img = Image.new("RGBA", (512, 512), (24, 24, 36, 255))
            draw = ImageDraw.Draw(img)
            draw.ellipse(
                (96, 96, 416, 416),
                fill=(255, 140, 66, 255),
                outline=(255, 255, 255, 255),
                width=8,
            )
            img.save(demo_img_path, "PNG")

        self.overlay.open_demo_mode([str(demo_img_path)])

    def start_conversion(self, action_id: str, action_label: str, file_paths: list[str]) -> None:
        """Open interactive Image Studio for `img_crop_edit` or dispatch worker to `QThreadPool`."""
        if action_id == "img_crop_edit" and file_paths:
            self._editor_dialog = ImageEditorDialog(file_paths[0])
            self._editor_dialog.image_saved.connect(
                lambda out_path: self.toast.show_success(
                    f"Saved {Path(out_path).name}",
                    output_path=out_path,
                )
            )
            self._editor_dialog.show()
            self._editor_dialog.raise_()
            self._editor_dialog.activateWindow()
            return

        worker = ConversionWorker(action_id, action_label, file_paths)
        worker.signals.started_job.connect(self.toast.show_progress)
        worker.signals.finished_job.connect(lambda res, w=worker: self._on_conversion_finished(res, w))
        self._active_workers.append(worker)
        self.thread_pool.start(worker)

    def _on_conversion_finished(self, result: ConversionResult, worker: ConversionWorker) -> None:
        if worker in self._active_workers:
            self._active_workers.remove(worker)

        if not result.success:
            self.toast.show_error(result.error_message or "Conversion failed")
            return

        if result.clipboard_text is not None:
            QGuiApplication.clipboard().setText(result.clipboard_text)
            self.toast.show_success(
                result.summary_text,
                output_path=None,
                sub_text="Copied to Windows Clipboard",
            )
            return

        first_output = result.output_paths[0] if result.output_paths else None
        self.toast.show_success(result.summary_text, output_path=first_output)

    def quit_app(self) -> None:
        self.watcher.set_enabled(False)
        self.overlay.close_overlay()
        if self._editor_dialog is not None:
            self._editor_dialog.close()
        self.toast.hide()
        self.tray.hide()
        self.app.quit()
