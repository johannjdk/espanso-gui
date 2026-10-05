"""Top-level application window coordinating focused editor modules."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QLabel, QMainWindow, QMessageBox, QSplitter

from ..config_service import ConfigService
from ..models import EspansoMatch
from ..runtime import application_icon
from ..ui.about_dialog import APP_NAME
from ..ui.search_dialog import SearchDialog
from ..ui.stats_dialog import StatsDialog
from .editor_ui import WindowLayoutMixin
from .file_management import FileManagementMixin
from .match_details import MatchDetailsMixin
from .match_management import MatchManagementMixin
from .menu import MenuMixin
from .playground import PlaygroundMixin


class MainWindow(MenuMixin, WindowLayoutMixin, FileManagementMixin, MatchManagementMixin, MatchDetailsMixin, PlaygroundMixin, QMainWindow):
    """Coordinate document state, focused editor modules, and top-level actions."""
    def __init__(self) -> None:
        super().__init__()
        self.config_path = ConfigService.detect_config_path()
        self.current_file: Path | None = None
        self.matches: list[EspansoMatch] = []
        self.document_extra: dict[str, object] = {}
        self.selected_match = -1
        self.selected_variable = -1
        self.selected_var_field = ""
        self.selected_form_field = ""
        self.dirty = False
        self._loading = False
        self._loading_var = False
        self._loading_var_field = False
        self._expanding = False
        self._playground_height = 180
        self._build_ui()
        self.load_files()
        self._set_editor_enabled(False)

    @property
    def dirty(self) -> bool:
        return self._dirty

    @dirty.setter
    def dirty(self, value: bool) -> None:
        self._dirty = value
        if hasattr(self, "file_label"):
            self._update_document_labels()

    def _update_document_labels(self) -> None:
        """Show the current file and whether its in-memory edits need saving."""
        if self.current_file is None:
            self.file_label.setText("No file selected")
            self.setWindowTitle(APP_NAME)
            return
        suffix = " — unsaved changes" if self.dirty else ""
        marker = " *" if self.dirty else ""
        self.file_label.setText(f"File: {self.current_file.name}{suffix}")
        self.setWindowTitle(f"{APP_NAME} — {self.current_file.name}{marker}")
    def _build_ui(self) -> None:
        self.resize(1280, 820)
        self.setWindowTitle(APP_NAME)
        self._load_window_icon()
        self._build_menu()
    def _load_window_icon(self) -> None:
        self.setWindowIcon(application_icon())

        self.horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.horizontal_splitter.addWidget(self._build_file_panel())
        self.horizontal_splitter.addWidget(self._build_editor_panel())
        self.horizontal_splitter.setSizes([360, 1040])

        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter.addWidget(self.horizontal_splitter)
        self.vertical_splitter.addWidget(self._build_playground_panel())
        self.vertical_splitter.setCollapsible(0, False)
        self.vertical_splitter.setCollapsible(1, False)

        handle = self.vertical_splitter.handle(1)
        if handle:
            handle.setEnabled(False)
            handle.setCursor(Qt.CursorShape.ArrowCursor)

        header_height = self.playground_header.sizeHint().height() + 2
        self.vertical_splitter.setSizes([1000, header_height])

        self.setCentralWidget(self.vertical_splitter)
        self.espanso_version = ConfigService.detect_espanso_version()
        ver_text = f"Espanso: {self.espanso_version}" if self.espanso_version else "Espanso: not detected"
        self.version_label = QLabel(ver_text)
        self.version_label.setEnabled(False)
        self.statusBar().addPermanentWidget(self.version_label)
        self.statusBar().showMessage(f"Configuration folder: {self.config_path}")

    def open_statistics(self) -> None:
        dialog = StatsDialog(self, getattr(self, "config_path", None))
        dialog.exec()

    def search_all_configurations(self) -> None:
        self.persist_current_match()
        dialog = SearchDialog(self, self.config_path, self.current_file, self.matches, self.open_search_match)
        dialog.exec()

    def open_search_match(self, path: Path, index: int) -> bool:
        if path != self.current_file:
            if not self._ask_save_changes():
                return False
            self.load_file(path)
            if self.current_file != path:
                return False
        self.persist_current_match()
        self.match_filter.clear()
        self.refresh_match_table(keep_selection=True)
        self._select_match(index)
        self.on_match_selected()
        self.load_files(selected_path=path)
        return True

    def _set_editor_enabled(self, enabled: bool) -> None:
        self.editor_content.setEnabled(enabled)
        self.match_sidebar.setEnabled(enabled)
        self._update_menu_actions()
        if not enabled:
            self.match_sidebar.setTitle("Matches")
            self._update_document_labels()
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
