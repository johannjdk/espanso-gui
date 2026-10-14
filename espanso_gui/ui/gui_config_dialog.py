"""Dialog for configuring the Espanso directory."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
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
        self.resize(500, 150)

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

        self.check_updates_cb = QCheckBox("Check for updates on startup")
        self.check_updates_cb.setChecked(ConfigService.get_check_updates())
        layout.addWidget(self.check_updates_cb)

        self.show_line_numbers_cb = QCheckBox("Show line numbers in editor")
        self.show_line_numbers_cb.setChecked(ConfigService.get_show_line_numbers())
        layout.addWidget(self.show_line_numbers_cb)

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
        self.check_updates_cb.setChecked(True)
        self.show_line_numbers_cb.setChecked(True)
        ConfigService.set_ignored_update_version("")

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
        ConfigService.set_check_updates(self.check_updates_cb.isChecked())
        ConfigService.set_show_line_numbers(self.show_line_numbers_cb.isChecked())
        self.accept()
