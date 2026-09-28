"""MatchManagementMixin."""

from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config_service import ConfigService
from ..models import EspansoMatch
from ..ui.move_match_dialog import choose_match_destination


class MatchManagementMixin:
    def persist_current_match(self) -> None:
        if self._loading or not (0 <= self.selected_match < len(self.matches)):
            return
        match = self.matches[self.selected_match]
        trigger_values = [self.trigger_edit.text().strip()]
        trigger_values.extend(edit.text().strip() for edit, _ in self.optional_trigger_edits)
        match.set_trigger_values(trigger_values, preserve_multiple=bool(match.triggers))
        match.word = self.word_check.isChecked()
        if self.radio_form.isChecked():
            match.mode = "form"
            match.form = self.form_layout_edit.toPlainText()
            match.replace = ""
        else:
            match.mode = "replace"
            match.replace = self.replace_edit.toPlainText()
            match.form = ""
    def add_optional_trigger(self, text: str = "") -> None:
        """Add an editable alias for the currently selected match."""
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        trigger_edit = QLineEdit(text)
        trigger_edit.setPlaceholderText("Additional trigger")
        trigger_edit.textChanged.connect(self._on_match_field_changed)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(lambda: self.remove_optional_trigger(row_widget))
        row.addWidget(trigger_edit)
        row.addWidget(remove_button)
        self.optional_trigger_edits.append((trigger_edit, row_widget))
        self.optional_trigger_layout.addWidget(row_widget)
    def remove_optional_trigger(self, row_widget: QWidget) -> None:
        self.optional_trigger_edits = [
            entry for entry in self.optional_trigger_edits if entry[1] is not row_widget
        ]
        self.optional_trigger_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        self._on_match_field_changed()
    def clear_optional_triggers(self) -> None:
        for _, row_widget in self.optional_trigger_edits:
            self.optional_trigger_layout.removeWidget(row_widget)
            row_widget.deleteLater()
        self.optional_trigger_edits.clear()
    def new_match(self) -> None:
        self.persist_current_match()
        self.matches.append(EspansoMatch(trigger=":new"))
        self.dirty = True
        self.refresh_match_table()
        row = len(self.matches) - 1
        self._select_match(row)
        self.trigger_edit.setFocus()
        self.trigger_edit.selectAll()
    def duplicate_match(self) -> None:
        if not (0 <= self.selected_match < len(self.matches)):
            return
        import copy

        self.persist_current_match()
        original = self.matches[self.selected_match]
        duplicate = copy.deepcopy(original)
        if original.triggers:
            duplicate.triggers = [f"{trigger}_copy" for trigger in original.triggers]
        else:
            duplicate.trigger = f"{original.trigger}_copy"
        self.matches.insert(self.selected_match + 1, duplicate)
        self.dirty = True
        self.refresh_match_table()
        self._select_match(self.selected_match + 1)
    def move_match(self) -> None:
        """Move the selected match to another Espanso match configuration file."""
        if self.current_file is None or not (0 <= self.selected_match < len(self.matches)):
            return

        source_path = self.current_file
        destinations = [
            path for path in sorted(self.config_path.glob("*.yml"), key=lambda path: path.name.lower())
            if path != source_path
        ]
        if not destinations:
            QMessageBox.information(
                self,
                "Move match",
                "Create another configuration file before moving a match.",
            )
            return
        destination_path = choose_match_destination(self, destinations)
        if destination_path is None:
            return

        self.move_match_to(destination_path, self.selected_match)
    def move_match_to(self, destination_path: Path, source_index: int) -> None:
        """Persist and move a match selected through the dialog or a drag operation."""
        if (
            self.current_file is None
            or destination_path == self.current_file
            or not (0 <= source_index < len(self.matches))
        ):
            return

        source_path = self.current_file
        self.persist_current_match()
        moved_match = self.matches[source_index]
        removed_from_source = False
        try:
            destination_matches, destination_extra = ConfigService.parse_yaml_document(destination_path)
            destination_matches.append(moved_match)
            ConfigService.save_yaml(destination_path, destination_matches, destination_extra)
            del self.matches[source_index]
            removed_from_source = True
            ConfigService.save_yaml(source_path, self.matches, self.document_extra)
        except (OSError, ValueError, __import__("yaml").YAMLError) as error:
            if removed_from_source:
                self.matches.insert(source_index, moved_match)
            QMessageBox.critical(self, "Move failed", f"Could not move the match:\n{error}")
            return

        self.load_files(selected_path=source_path)
        self.load_file(source_path)
        self.statusBar().showMessage(f"Moved match to {destination_path.name}", 4000)
    def delete_match(self) -> None:
        if not (0 <= self.selected_match < len(self.matches)):
            return
        if (
            QMessageBox.question(
                self,
                "Delete match",
                "Really delete this match?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        del self.matches[self.selected_match]
        self.selected_match = -1
        self.dirty = True
        self.refresh_match_table()
        if self.matches:
            self._select_match(0)
        else:
            self.clear_match_form()
            self.match_editor_box.setEnabled(False)
            self.delete_match_btn.setEnabled(False)
    def refresh_match_table(self, keep_selection: bool = False) -> None:
        self._loading = True
        prev_row = self.selected_match if keep_selection else -1
        if not keep_selection:
            # Qt otherwise retains a selected row at the same position when a
            # different file is loaded, so no selection event is emitted.
            self.match_table.clearSelection()
        query = self.match_filter.text().strip().casefold()
        visible_matches = [
            (index, match) for index, match in enumerate(self.matches)
            if not query or query in f"{match.trigger_text} {'Form' if match.is_form else 'Replace'} {match.preview}".casefold()
        ]
        self.match_table.setSortingEnabled(False)
        self.match_table.setRowCount(len(visible_matches))
        for row, (index, match) in enumerate(visible_matches):
            type_str = "Form" if match.is_form else "Replace"
            for column, value in enumerate((match.trigger_text, type_str)):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.match_table.setItem(row, column, item)
        self.match_table.setSortingEnabled(True)
        if 0 <= prev_row < len(self.matches):
            self._select_match(prev_row)
        self._loading = False
    def _select_match(self, match_index: int) -> None:
        for row in range(self.match_table.rowCount()):
            item = self.match_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == match_index:
                self.match_table.selectRow(row)
                return
    def on_mode_toggled(self) -> None:
        is_form = self.radio_form.isChecked()
        self.content_stack.setCurrentIndex(1 if is_form else 0)
        self.details_tabs.setCurrentIndex(0)
        if not self._loading and 0 <= self.selected_match < len(self.matches):
            # A new mode starts empty; hidden editors must not restore old text.
            self._loading = True
            self.replace_edit.clear()
            self.form_layout_edit.clear()
            self._loading = False
            self.persist_current_match()
            self.dirty = True
            self.refresh_match_table(keep_selection=True)
    def on_match_selected(self) -> None:
        if self._loading:
            return
        self.persist_current_match()
        rows = self.match_table.selectionModel().selectedRows()
        if not rows:
            self.selected_match = -1
            self.match_editor_box.setEnabled(False)
            self.delete_match_btn.setEnabled(False)
            return
        item = self.match_table.item(rows[0].row(), 0)
        if item is None:
            return
        self.selected_match = item.data(Qt.ItemDataRole.UserRole)
        self.selected_variable = -1
        self.selected_form_field = ""
        self.match_editor_box.setEnabled(True)
        self.delete_match_btn.setEnabled(True)
        match = self.matches[self.selected_match]

        self._loading = True
        self.clear_optional_triggers()
        if match.triggers:
            self.trigger_edit.setText(match.triggers[0] if match.triggers else "")
            for trigger in match.triggers[1:]:
                self.add_optional_trigger(trigger)
        else:
            self.trigger_edit.setText(match.trigger)
        self.word_check.setChecked(match.word)
        # Refresh hidden content too, so it cannot leak between matches.
        self.replace_edit.setPlainText(match.replace)
        self.form_layout_edit.setPlainText(match.form)
        if match.is_form:
            self.radio_form.setChecked(True)
            self.content_stack.setCurrentIndex(1)
        else:
            self.radio_replace.setChecked(True)
            self.content_stack.setCurrentIndex(0)
        self._loading = False

        self.refresh_form_fields_table()
        self.clear_form_field_form()
        self.refresh_variable_table()
        self.clear_variable_form()
    def clear_match_form(self) -> None:
        self._loading = True
        self.trigger_edit.clear()
        self.clear_optional_triggers()
        self.replace_edit.clear()
        self.form_layout_edit.clear()
        self.radio_replace.setChecked(True)
        self.content_stack.setCurrentIndex(0)
        self.details_tabs.setCurrentIndex(0)
        self.word_check.setChecked(False)
        self._loading = False
        self.refresh_form_fields_table()
        self.clear_form_field_form()
        self.refresh_variable_table()
        self.clear_variable_form()
