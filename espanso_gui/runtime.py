"""Qt runtime and desktop integration helpers."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QListWidget,
    QMessageBox, QPushButton, QRadioButton, QScrollArea, QSplitter,
    QPlainTextEdit, QStackedWidget, QStyleFactory, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .config_service import ConfigService
from .models import EspansoFormField, EspansoMatch, EspansoVariable
from .ui.about_dialog import APP_ID, APP_NAME, show_about_dialog
from .ui.match_drag_drop import MatchFileTreeWidget, MatchTableWidget
from .ui.move_match_dialog import choose_match_destination


def application_icon() -> QIcon:
    """Return the packaged application icon when one is available."""
    resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    candidates = [
        resource_root / "assets" / "espanso-gui-qt.png",
        Path(f"/usr/share/icons/hicolor/256x256/apps/{APP_ID}.png"),
        Path(f"/usr/share/pixmaps/{APP_ID}.png"),
        # Compatibility with packages built before the standard-size path.
        Path(f"/usr/share/icons/hicolor/160x160/apps/{APP_ID}.png"),
    ]
    for icon_path in candidates:
        if icon_path.is_file():
            return QIcon(str(icon_path))
    return QIcon()


def setup_qt_environment() -> None:
    """Register system Qt6 plugin directories and desktop platform integration."""
    if not sys.platform.startswith("linux"):
        return

    # On Linux, register system Qt6 plugin directories (e.g. /usr/lib/qt6/plugins)
    # so that pip wheels can load system styles (like Breeze) and platform themes.
    qt6_plugin_dirs = [
        "/usr/lib/qt6/plugins",
        "/usr/lib64/qt6/plugins",
        "/usr/lib/x86_64-linux-gnu/qt6/plugins",
        "/usr/lib/aarch64-linux-gnu/qt6/plugins",
        "/usr/local/lib/qt6/plugins",
    ]
    valid_dirs = [d for d in qt6_plugin_dirs if os.path.isdir(d)]
    for d in valid_dirs:
        QCoreApplication.addLibraryPath(d)

    if valid_dirs:
        existing = os.environ.get("QT_PLUGIN_PATH", "")
        existing_list = [p for p in existing.split(os.pathsep) if p]
        new_dirs = [d for d in valid_dirs if d not in existing_list]
        if new_dirs:
            os.environ["QT_PLUGIN_PATH"] = os.pathsep.join(new_dirs + existing_list)

    # In KDE Plasma sessions, ensure QT_QPA_PLATFORMTHEME is set to 'kde'
    # so that Qt integrates with KDE fonts, colors, and Breeze widgets.
    is_kde = os.environ.get("KDE_FULL_SESSION") == "true" or "KDE" in os.environ.get(
        "XDG_CURRENT_DESKTOP", ""
    )
    if is_kde and "QT_QPA_PLATFORMTHEME" not in os.environ:
        os.environ["QT_QPA_PLATFORMTHEME"] = "kde"


def _detect_desktop_style() -> str:
    """Detect the user's preferred desktop style (e.g. Breeze on KDE Plasma)."""
    # 1. Check explicit QT_STYLE_OVERRIDE environment variable
    override = os.environ.get("QT_STYLE_OVERRIDE", "").strip()
    if override:
        return override

    # 2. Check KDE Plasma settings if running under KDE
    is_kde = os.environ.get("KDE_FULL_SESSION") == "true" or "KDE" in os.environ.get(
        "XDG_CURRENT_DESKTOP", ""
    )
    if is_kde:
        for cmd in ("kreadconfig6", "kreadconfig5"):
            if shutil.which(cmd):
                try:
                    res = subprocess.run(
                        [cmd, "--group", "KDE", "--key", "widgetStyle"],
                        capture_output=True,
                        text=True,
                        timeout=1,
                        check=False,
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        return res.stdout.strip()
                except Exception:
                    pass

        # Fallback to checking ~/.config/kdeglobals directly
        config_file = Path.home() / ".config" / "kdeglobals"
        if config_file.is_file():
            try:
                in_kde_group = False
                for line in config_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line.startswith("[") and line.endswith("]"):
                        in_kde_group = line.lower() == "[kde]"
                    elif in_kde_group and line.lower().startswith("widgetstyle="):
                        val = line.split("=", 1)[1].strip()
                        if val:
                            return val
            except Exception:
                pass

        # Default on KDE Plasma is Breeze
        return "Breeze"

    return ""


