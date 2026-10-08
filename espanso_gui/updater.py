"""Check for Espanso GUI updates on GitHub."""

from __future__ import annotations

import json
import re
import os
import ssl
import urllib.request

from PySide6.QtCore import QObject, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget

from .config_service import ConfigService

GITHUB_RELEASES_API = "https://api.github.com/repos/johannjdk/espanso-gui/releases/latest"
GITHUB_RELEASES_WEB = "https://github.com/johannjdk/espanso-gui/releases"


def get_ssl_context() -> ssl.SSLContext:
    """Create an SSL context with certificates from certifi or known system locations."""
    try:
        import certifi

        cafile = certifi.where()
        if os.path.isfile(cafile):
            return ssl.create_default_context(cafile=cafile)
    except Exception:
        pass

    for cafile in (
        "/etc/ssl/cert.pem",                   # macOS default
        "/etc/pki/tls/certs/ca-bundle.crt",   # Fedora/RHEL
        "/etc/ssl/certs/ca-certificates.crt", # Debian/Ubuntu
    ):
        if os.path.isfile(cafile):
            try:
                return ssl.create_default_context(cafile=cafile)
            except Exception:
                pass

    return ssl.create_default_context()


def parse_version(version: str) -> tuple[int, ...]:
    """Parse a semantic version string into a numeric tuple for comparison."""
    parts = [int(p) for p in re.findall(r"\d+", version.strip().lstrip("vV"))]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


class UpdateCheckThread(QThread):
    """Background worker to check GitHub releases without blocking the UI."""

    update_available = Signal(str, str)
    up_to_date = Signal()
    check_failed = Signal(str)

    def __init__(self, current_version: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.current_version = current_version

    def run(self) -> None:
        try:
            req = urllib.request.Request(
                GITHUB_RELEASES_API,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            ssl_context = get_ssl_context()
            with urllib.request.urlopen(req, timeout=4, context=ssl_context) as response:
                data = json.loads(response.read().decode("utf-8"))

            tag = str(data.get("tag_name", "")).strip()
            url = str(data.get("html_url", GITHUB_RELEASES_WEB)).strip() or GITHUB_RELEASES_WEB

            if tag and parse_version(tag) > parse_version(self.current_version):
                self.update_available.emit(tag, url)
            else:
                self.up_to_date.emit()
        except Exception as exc:
            self.check_failed.emit(str(exc))


def check_for_updates(
    parent: QWidget, current_version: str, *, manual: bool = False
) -> UpdateCheckThread | None:
    """Check for updates asynchronously and notify the user if an update is found."""
    if not manual and not ConfigService.get_check_updates():
        return None

    thread = UpdateCheckThread(current_version, parent)

    def on_available(new_version: str, url: str) -> None:
        if not manual:
            ignored = ConfigService.get_ignored_update_version()
            if ignored and parse_version(new_version) <= parse_version(ignored):
                return

        msg = QMessageBox(parent)
        msg.setWindowTitle("Update Available")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("<b>A new version of Espanso GUI is available!</b>")
        msg.setInformativeText(
            f"Installed version: v{current_version}\n"
            f"Latest version: {new_version}\n\n"
            f"Would you like to open the release page?"
        )
        open_btn = msg.addButton("Open Release", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(open_btn)
        msg.exec()
        ConfigService.set_ignored_update_version(new_version)
        if msg.clickedButton() == open_btn:
            QDesktopServices.openUrl(QUrl(url))

    def on_up_to_date() -> None:
        if manual:
            QMessageBox.information(
                parent,
                "No Updates Available",
                f"You are using the latest version of Espanso GUI (v{current_version}).",
            )

    def on_failed(error_msg: str) -> None:
        if manual:
            QMessageBox.warning(
                parent,
                "Update Check Failed",
                f"Could not check for updates:\n{error_msg}",
            )

    thread.update_available.connect(on_available)
    thread.up_to_date.connect(on_up_to_date)
    thread.check_failed.connect(on_failed)
    thread.start()
    return thread
