"""Top-level application window coordinating focused editor modules."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import QMainWindow, QSplitter

from ..config_service import ConfigService
from ..models import EspansoMatch
from ..runtime import application_icon
from ..ui.about_dialog import APP_NAME, show_about_dialog
from .editor_ui import WindowLayoutMixin
from .file_management import FileManagementMixin
from .match_details import MatchDetailsMixin
from .match_management import MatchManagementMixin


class MainWindow(WindowLayoutMixin, FileManagementMixin, MatchManagementMixin, MatchDetailsMixin, QMainWindow):
    """Coordinate document state, focused editor modules, and top-level actions."""
    def __init__(self) -> None:
        super().__init__()
        self.config_path = ConfigService.detect_config_path()
        self.current_file: Path | None = None
        self.matches: list[EspansoMatch] = []
        self.document_extra: dict[str, object] = {}
        self.selected_match = -1
        self.selected_variable = -1
        self.selected_form_field = ""
        self.dirty = False
        self._loading = False
        self._build_ui()
        self.load_files()
        self._set_editor_enabled(False)
    def _build_ui(self) -> None:
        self.resize(1280, 820)
        self.setWindowTitle(APP_NAME)
        self._load_window_icon()
        self._build_menu()
    def _load_window_icon(self) -> None:
        self.setWindowIcon(application_icon())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_file_panel())
        splitter.addWidget(self._build_editor_panel())
        splitter.setSizes([360, 1040])
        self.setCentralWidget(splitter)
        self.statusBar().showMessage(f"Configuration folder: {self.config_path}")
    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("File")
        save = QAction("Save", self)
        save.setShortcut("Ctrl+S")
        save.triggered.connect(self.save_current_file)
        new_config = QAction("New configuration", self)
        new_config.setShortcut("Ctrl+N")
        new_config.triggered.connect(self.new_file)
        expert_yaml = QAction("Expert YAML…", self)
        expert_yaml.setShortcut("Ctrl+E")
        expert_yaml.triggered.connect(self.open_yaml_editor)
        espanso_config = QAction("Espanso configuration…", self)
        espanso_config.triggered.connect(self.open_espanso_configuration)
        menu.addActions([new_config, save, expert_yaml, espanso_config])

        edit_menu = self.menuBar().addMenu("Edit")
        duplicate = QAction("Duplicate match", self)
        duplicate.setShortcut("Ctrl+D")
        duplicate.triggered.connect(self.duplicate_match)
        edit_menu.addAction(duplicate)

        help_menu = self.menuBar().addMenu("Help")
        about = QAction("About Espanso GUI", self)
        about.triggered.connect(lambda: show_about_dialog(self, self.config_path))
        help_menu.addAction(about)
    def _set_editor_enabled(self, enabled: bool) -> None:
        self.editor_content.setEnabled(enabled)
        self.match_sidebar.setEnabled(enabled)
        if not enabled:
            self.file_label.setText("No file selected")
            self.match_sidebar.setTitle("Matches")
            self.setWindowTitle(APP_NAME)
    def _on_match_field_changed(self) -> None:
        if not self._loading and 0 <= self.selected_match < len(self.matches):
            self.dirty = True
    def save_current_file(self) -> bool:
        if self.current_file is None:
            return False
        self.persist_current_match()
        try:
            ConfigService.save_yaml(self.current_file, self.matches, self.document_extra)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Save error", f"Could not save {self.current_file.name}:\n{error}")
            return False
        self.dirty = False
        self.refresh_match_table(keep_selection=True)
        self.statusBar().showMessage(f"Saved {self.current_file.name}", 4000)
        return True
    def restart_espanso(self) -> None:
        try:
            result = ConfigService.restart_espanso()
        except (OSError, TimeoutError) as error:
            QMessageBox.critical(self, "Restart failed", f"Could not run espanso:\n{error}")
            return
        if result.returncode == 0:
            QMessageBox.information(self, "Espanso restarted", "Espanso has been restarted.")
        else:
            detail = result.stderr.strip() or result.stdout.strip() or f"Exit code {result.returncode}"
            QMessageBox.warning(self, "Restart failed", detail)
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._ask_save_changes():
            event.accept()
        else:
            event.ignore()
