"""Application entry point for Espanso GUI."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QStyleFactory

from .runtime import _detect_desktop_style, application_icon, setup_qt_environment
from .ui.about_dialog import APP_ID, APP_NAME
from .windows.main_window import MainWindow


def main() -> int:
    """Create the Qt application and show the main window."""
    setup_qt_environment()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(application_icon())
    if not any(arg in sys.argv for arg in ("-style", "--style")):
        preferred_style = _detect_desktop_style()
        styles = {name.lower(): name for name in QStyleFactory.keys()}
        if preferred_style and preferred_style.lower() in styles:
            app.setStyle(styles[preferred_style.lower()])
        elif "breeze" in styles and app.style().objectName().lower() in ("fusion", "windows"):
            app.setStyle(styles["breeze"])
    window = MainWindow()
    window.show()
    return app.exec()


__all__ = ["main"]
