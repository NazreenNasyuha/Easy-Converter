"""Easy Converter — Zero-Click Shift-Drag Radial File Converter for Windows 11.

Application bootstrap, CLI argument parsing, High-DPI configuration, and single-instance guard.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QLockFile, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from core.config import APP_NAME, APP_ORG, SINGLE_INSTANCE_LOCK_NAME
from core.ui.tray_controller import EasyConverterController


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options for Easy Converter."""
    parser = argparse.ArgumentParser(description=f"{APP_NAME} — Radial File Converter")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the automated unit & integration test suite and exit",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Open the radial overlay in Demo Mode immediately on startup",
    )
    parser.add_argument(
        "--auto-exit-ms",
        type=int,
        default=0,
        help="Automatically exit after N milliseconds (used for automated GUI smoke tests)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Bootstrap and run the Easy Converter desktop utility."""
    args = parse_args(argv)

    if args.self_test:
        from tests.test_engine import run_cli_self_test

        return run_cli_self_test()

    # Windows 11 High-DPI PassThrough rounding policy (125% / 150% fractional scaling)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    app.setQuitOnLastWindowClosed(False)

    # Single-instance lock
    lock_path = Path(tempfile.gettempdir()) / SINGLE_INSTANCE_LOCK_NAME
    lock_file = QLockFile(str(lock_path))
    lock_file.setStaleLockTime(0)
    if not lock_file.tryLock(100):
        print(f"{APP_NAME} is already running in the Windows system tray.")
        return 0

    controller = EasyConverterController(app)

    if args.demo:
        QTimer.singleShot(150, controller.launch_demo_mode)
    else:
        QTimer.singleShot(
            250,
            lambda: controller.toast.show_success(
                f"{APP_NAME} Ready",
                sub_text="Drag any file + press Shift / Alt / Ctrl",
                duration_ms=2400,
            ),
        )

    if args.auto_exit_ms > 0:
        QTimer.singleShot(args.auto_exit_ms, controller.quit_app)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
