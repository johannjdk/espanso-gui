"""Application identity and the Help → About dialog."""

from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget

from .. import __version__


APP_NAME = "Espanso GUI"
APP_ID = "io.github.johannjdk.EspansoGui"
PROJECT_URL = "https://github.com/johannjdk/espanso-gui"
ESPANSO_URL = "https://espanso.org/"


def show_about_dialog(
    parent: QWidget, configuration_path: Path, espanso_version: str | None = None
) -> None:
    """Show application details and links useful to users and bug reporters."""
    ver_line = f"<p><b>Espanso version:</b> {escape(espanso_version)}</p>" if espanso_version else ""
    QMessageBox.about(
        parent,
        f"About {APP_NAME}",
        f"""
        <h2>{APP_NAME}</h2>
        <p>A desktop editor for Espanso match files.</p>
        <p><b>Version:</b> {escape(__version__)}</p>
        {ver_line}
        <p><b>Configuration folder:</b><br>{escape(str(configuration_path))}</p>
        <p><a href=\"{PROJECT_URL}\">Project and issue tracker</a><br>
        <a href=\"{ESPANSO_URL}\">Espanso documentation</a></p>
        <p><small>Espanso GUI is an independent project and is not affiliated with Espanso.</small></p>
        """,
    )
