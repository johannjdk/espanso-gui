"""Dialog for Espanso application profiles."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget)

from ..config_service import ConfigService


class EspansoConfigDialog(QDialog):
    """Edit Espanso's default and application-specific configuration profiles."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config_dir = ConfigService.detect_options_path()
        self.current_path: Path | None = None

        self.setWindowTitle("Espanso configuration")
        self.resize(980, 680)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Edit Espanso configuration profiles. <b>default.yml</b> applies everywhere; "
            "other profiles become active when their filter rules match an application."
        ))

        content = QSplitter(Qt.Orientation.Horizontal)
        file_panel = QWidget()
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.addWidget(QLabel("Configuration profiles"))
        self.profile_list = QListWidget()
        self.profile_list.currentTextChanged.connect(self._select_profile)
        file_layout.addWidget(self.profile_list, 1)

        profile_buttons = QHBoxLayout()
        new_profile = QPushButton("New…")
        delete_profile = QPushButton("Delete")
        new_profile.clicked.connect(self.new_profile)
        delete_profile.clicked.connect(self.delete_profile)
        profile_buttons.addWidget(new_profile)
        profile_buttons.addWidget(delete_profile)
        file_layout.addLayout(profile_buttons)
        content.addWidget(file_panel)

        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        self.profile_label = QLabel("No profile selected")
        editor_layout.addWidget(self.profile_label)
        editor_layout.addWidget(QLabel(
            "Use filter_exec, filter_class, filter_title, or filter_os for app profiles. "
            "Includes and excludes accept the standard and extra_ variants. "
            "App-specific profiles are not supported by Espanso on Wayland."
        ))
        self.editor = QPlainTextEdit()
        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(" ") * 2)
        editor_layout.addWidget(self.editor, 1)
        content.addWidget(editor_panel)
        content.setSizes([260, 720])
        layout.addWidget(content, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        buttons.accepted.connect(self.save_current_profile)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self._load_profiles()

    def _load_profiles(self, selected_path: Path | None = None) -> None:
        paths: list[Path] = []
        if self.config_dir.is_dir():
            paths = sorted(self.config_dir.glob("*.yml"), key=lambda path: path.name.lower())
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        for path in paths:
            self.profile_list.addItem(path.name)
        self.profile_list.blockSignals(False)

        target = selected_path or self.current_path
        if target is not None and target in paths:
            self.profile_list.setCurrentRow(paths.index(target))
        elif paths:
            self.profile_list.setCurrentRow(0)
        else:
            self.current_path = None
            self.profile_label.setText("No profile selected")
            self.editor.clear()
            self.editor.setEnabled(False)
            self.save_button.setEnabled(False)

    def _select_profile(self, name: str) -> None:
        if not name:
            return
        path = self.config_dir / name
        if path == self.current_path:
            return
        if not self._confirm_profile_change():
            self.profile_list.blockSignals(True)
            if self.current_path is not None:
                matches = self.profile_list.findItems(
                    self.current_path.name, Qt.MatchFlag.MatchExactly
                )
                if matches:
                    self.profile_list.setCurrentItem(matches[0])
            self.profile_list.blockSignals(False)
            return
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(self, "Open failed", str(error))
            return
        self.current_path = path
        self.profile_label.setText(f"Editing: {path.name}")
        self.editor.setEnabled(True)
        self.editor.setPlainText(source)
        self.editor.document().setModified(False)
        self.save_button.setEnabled(True)

    def _confirm_profile_change(self) -> bool:
        if self.current_path is None or not self.editor.document().isModified():
            return True
        answer = QMessageBox.warning(
            self,
            "Unsaved configuration",
            f"Save changes to {self.current_path.name}?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return answer != QMessageBox.StandardButton.Save or self.save_current_profile()

    def new_profile(self) -> None:
        name, accepted = QInputDialog.getText(self, "New configuration profile", "File name (.yml):")
        if not accepted or not name.strip():
            return
        name = name.strip()
        if not name.endswith(".yml"):
            name += ".yml"
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.yml", name):
            QMessageBox.warning(self, "Invalid name", "Use a simple filename ending in .yml.")
            return
        path = self.config_dir / name
        if path.exists():
            QMessageBox.warning(self, "Already exists", f"{name} already exists.")
            return
        try:
            ConfigService.save_config_yaml(path, "# Espanso configuration profile\n")
        except OSError as error:
            QMessageBox.critical(self, "Create failed", str(error))
            return
        self._load_profiles(path)

    def delete_profile(self) -> None:
        if self.current_path is None:
            return
        if not self._confirm_profile_change():
            return
        path = self.current_path
        if (
            QMessageBox.question(
                self,
                "Delete configuration profile",
                f'Really delete "{path.name}"?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            path.unlink()
        except OSError as error:
            QMessageBox.critical(self, "Delete failed", str(error))
            return
        self.current_path = None
        self._load_profiles()

    def save_current_profile(self) -> bool:
        if self.current_path is None:
            return False
        try:
            ConfigService.save_config_yaml(self.current_path, self.editor.toPlainText())
        except (OSError, ValueError, __import__("yaml").YAMLError) as error:
            QMessageBox.critical(self, "Invalid configuration", str(error))
            return False
        self.editor.document().setModified(False)
        return True

    def reject(self) -> None:
        if self._confirm_profile_change():
            super().reject()
