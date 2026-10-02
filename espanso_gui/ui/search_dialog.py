"""Search matches across the configuration directory."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import yaml
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHeaderView, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..config_service import ConfigService
from ..models import EspansoMatch


class SearchDialog(QDialog):
    def __init__(
        self, parent: QWidget, directory: Path, current_file: Path | None,
        current_matches: list[EspansoMatch], open_match: Callable[[Path, int], bool],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Search all configurations")
        self.resize(850, 500)
        self.directory = directory
        self.open_match = open_match
        self.entries: list[tuple[Path, int, EspansoMatch, str]] = []
        errors = []
        paths = ConfigService.match_files(directory)
        if current_file is not None and current_file not in paths:
            paths.append(current_file)
        for path in paths:
            try:
                matches = current_matches if path == current_file else ConfigService.parse_yaml(path)
            except (OSError, ValueError, TypeError, yaml.YAMLError) as error:
                errors.append(f"{path.relative_to(directory)}: {error}")
                continue
            filename = path.relative_to(directory).as_posix()
            for index, match in enumerate(matches):
                self.entries.append((path, index, match, f"{filename.casefold()} {match.search_text}"))

        layout = QVBoxLayout(self)
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search all match files…")
        self.query.setToolTip("Search file names, triggers, types, full content, and variables")
        self.query.setClearButtonEnabled(True)
        layout.addWidget(self.query)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["File", "Trigger", "Type", "Content"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table, 1)
        self.count = QLabel()
        layout.addWidget(self.count)
        if errors:
            warning = QLabel(f"Skipped {len(errors)} unreadable file(s). Hover for details.")
            warning.setToolTip("\n".join(errors))
            layout.addWidget(warning)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Close)
        self.open_button = buttons.button(QDialogButtonBox.StandardButton.Open)
        buttons.accepted.connect(self.open_selected)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.query.textChanged.connect(self.refresh_results)
        self.table.itemSelectionChanged.connect(
            lambda: self.open_button.setEnabled(bool(self.table.selectedItems()))
        )
        self.table.itemActivated.connect(lambda _: self.open_selected())
        self.refresh_results()
        self.query.setFocus()

    def refresh_results(self) -> None:
        query = self.query.text().strip().casefold()
        results = [entry for entry in self.entries if query and query in entry[3]]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(results))
        for row, (path, index, match, _) in enumerate(results):
            values = (path.relative_to(self.directory).as_posix(), match.trigger_text,
                      "Form" if match.is_form else "Replace", match.preview)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, (path, index))
                item.setToolTip(match.form if match.is_form else match.replace)
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)
        self.open_button.setEnabled(False)
        if results:
            self.table.selectRow(0)
        self.count.setText(f"{len(results)} match(es)" if query else "Enter a search term.")

    def open_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        path, index = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if self.open_match(path, index):
            self.accept()
