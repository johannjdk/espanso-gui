"""Dialog for configuring the Espanso directory."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config_service import ConfigService


class EspansoGuiConfigDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Espanso GUI Configuration")
        self.resize(500, 120)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(".espanso directory:"))

        row = QHBoxLayout()
        current = ConfigService.get_custom_espanso_path() or ConfigService.detect_espanso_path()
        self.path_edit = QLineEdit(str(current))
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        row.addWidget(self.path_edit)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._restore_defaults)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Select .espanso directory", self.path_edit.text())
        if dir_path:
            self.path_edit.setText(dir_path)

    def _restore_defaults(self) -> None:
        self.path_edit.setText(str(ConfigService.default_espanso_path()))

    def _save(self) -> None:
        path_str = self.path_edit.text().strip()
        if not path_str:
            return
        path = Path(path_str)
        if not path.is_dir():
            QMessageBox.warning(self, "Invalid directory", "The selected directory does not exist.")
            return
        if path == ConfigService.default_espanso_path():
            ConfigService.set_custom_espanso_path(None)
        else:
            ConfigService.set_custom_espanso_path(path)
        self.accept()
