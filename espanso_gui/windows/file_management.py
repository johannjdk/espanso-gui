"""FileManagementMixin."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QInputDialog, QLabel, QMessageBox, QPlainTextEdit, QTreeWidgetItem, QVBoxLayout

from ..config_service import ConfigService
from ..ui.about_dialog import APP_NAME
from .profile_dialog import EspansoConfigDialog


class FileManagementMixin:
    def load_files(self, selected_path: Path | None = None) -> None:
        self.file_tree.blockSignals(True)
        self.file_tree.clear()
        root = QTreeWidgetItem(["Configs"])
        root.setData(0, Qt.ItemDataRole.UserRole, None)
        self.file_tree.addTopLevelItem(root)
        if self.config_path.is_dir():
            for path in ConfigService.match_files(self.config_path):
                item = QTreeWidgetItem([path.relative_to(self.config_path).as_posix()])
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                root.addChild(item)
                if path == selected_path:
                    self.file_tree.setCurrentItem(item)
        root.setExpanded(True)
        self.file_tree.blockSignals(False)
    def _ask_save_changes(self) -> bool:
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            "Save changes before continuing?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return answer != QMessageBox.StandardButton.Yes or self.save_current_file()
    def on_file_selected(self) -> None:
        selected = self.file_tree.selectedItems()
        if not selected:
            return
        path = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(path, Path) or path == self.current_file:
            return
        if not self._ask_save_changes():
            self.file_tree.blockSignals(True)
            self.file_tree.clearSelection()
            self.file_tree.blockSignals(False)
            return
        self.load_file(path)
    def load_file(self, path: Path) -> None:
        try:
            self.matches, self.document_extra = ConfigService.parse_yaml_document(path)
        except (OSError, ValueError, __import__("yaml").YAMLError) as error:
            QMessageBox.critical(self, "Parse error", f"Could not load {path.name}:\n{error}")
            return
        self.current_file = path
        self.dirty = False
        self.selected_match = -1
        self.file_label.setText(f"File: {path.name}")
        self.match_sidebar.setTitle(f"Matches — {path.name}")
        self.setWindowTitle(f"{APP_NAME} — {path.name}")
        self._set_editor_enabled(True)
        self.refresh_match_table()
        if self.matches:
            self._select_match(0)
            self.on_match_selected()
        else:
            self.clear_match_form()
            self.match_editor_box.setEnabled(False)
            self.delete_match_btn.setEnabled(False)
    def new_file(self) -> None:
        name, accepted = QInputDialog.getText(self, "New configuration", "File name (.yml):")
        if not accepted or not name.strip():
            return
        name = name.strip()
        if not name.endswith(".yml"):
            name += ".yml"
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.yml", name):
            QMessageBox.warning(self, "Invalid name", "Use a simple filename ending in .yml.")
            return
        path = self.config_path / name
        if path.exists():
            QMessageBox.warning(self, "Already exists", f"{name} already exists.")
            return
        try:
            ConfigService.save_yaml(path, [])
        except OSError as error:
            QMessageBox.critical(self, "Create failed", str(error))
            return
        self.load_files()
        self.load_file(path)
    def delete_file(self) -> None:
        selected = self.file_tree.selectedItems()
        if not selected or not isinstance(selected[0].data(0, Qt.ItemDataRole.UserRole), Path):
            return
        path: Path = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if (
            QMessageBox.question(
                self,
                "Delete configuration",
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
        if path == self.current_file:
            self.current_file = None
            self.matches = []
            self.document_extra = {}
            self.dirty = False
            self._set_editor_enabled(False)
        self.load_files()
    def open_yaml_editor(self) -> None:
        """Open the complete YAML file for advanced Espanso options."""
        if self.current_file is None:
            return
        if not self._ask_save_changes():
            return
        try:
            source = self.current_file.read_text(encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(self, "Open failed", str(error))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Expert YAML — {self.current_file.name}")
        dialog.resize(900, 650)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Edit the full Espanso YAML document. It is validated before saving."))
        editor = QPlainTextEdit()
        editor.setPlainText(source)
        editor.setTabStopDistance(editor.fontMetrics().horizontalAdvance(" ") * 2)
        layout.addWidget(editor, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.rejected.connect(dialog.reject)

        def save_expert_yaml() -> None:
            path = self.current_file
            try:
                ConfigService.save_raw_yaml(path, editor.toPlainText())
                self.load_files(selected_path=path)
                self.load_file(path)
            except (OSError, ValueError, __import__("yaml").YAMLError) as error:
                QMessageBox.critical(dialog, "Invalid YAML", str(error))
                return
            self.statusBar().showMessage(f"Saved {self.current_file.name}", 4000)
            dialog.accept()

        buttons.accepted.connect(save_expert_yaml)
        layout.addWidget(buttons)
        dialog.exec()
    def open_espanso_configuration(self) -> None:
        """Open Espanso's config directory without mixing profiles with match files."""
        if not self._ask_save_changes():
            return
        dialog = EspansoConfigDialog(self)
        dialog.exec()
