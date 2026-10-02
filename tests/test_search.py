import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from espanso_gui.config_service import ConfigService
from espanso_gui.models import EspansoMatch, EspansoVariable
from espanso_gui.ui.search_dialog import SearchDialog
from espanso_gui.windows.main_window import MainWindow


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.first = self.directory / "base.yml"
        self.second = self.directory / "packages" / "other.yaml"
        ConfigService.save_yaml(self.first, [EspansoMatch(trigger=":first", replace="original")])
        ConfigService.save_yaml(self.second, [
            EspansoMatch(trigger=":z", replace="x" * 100 + "Straße\nlast line"),
            EspansoMatch(triggers=[":a", ":alias"], form="Hello [[name]]", mode="form",
                         variables=[EspansoVariable(name="lookup", params={"cmd": "special-command"})]),
        ])
        with patch.object(ConfigService, "detect_config_path", return_value=self.directory):
            self.window = MainWindow()
        self.addCleanup(self.window.deleteLater)

    def dialog(self):
        self.window.persist_current_match()
        dialog = SearchDialog(self.window, self.directory, self.window.current_file,
                              self.window.matches, self.window.open_search_match)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_full_content_alias_variables_and_nested_filename(self):
        dialog = self.dialog()
        for query, count in [("STRASSE", 1), ("Straße\nlast line", 1), (":alias", 1),
                             ("special-command", 1), ("packages/other.yaml", 2),
                             ("form", 1), ("missing", 0), ("  ", 0)]:
            with self.subTest(query=query):
                dialog.query.setText(query)
                self.assertEqual(dialog.table.rowCount(), count)
                self.assertEqual(dialog.open_button.isEnabled(), count > 0)

    def test_sorted_result_opens_correct_match_and_clears_local_filter(self):
        self.window.load_file(self.first)
        self.window.match_filter.setText("original")
        dialog = self.dialog()
        dialog.query.setText("packages")
        dialog.table.sortItems(1, Qt.SortOrder.AscendingOrder)
        dialog.table.selectRow(0)
        dialog.open_selected()
        self.assertEqual(self.window.current_file, self.second)
        self.assertEqual(self.window.selected_match, 1)
        self.assertEqual(self.window.trigger_edit.text(), ":a")
        self.assertEqual(self.window.match_filter.text(), "")
        self.assertEqual(self.window.file_tree.currentItem().text(0), "packages/other.yaml")

    def test_unsaved_edits_are_searchable_without_writing(self):
        self.window.load_file(self.first)
        self.window.replace_edit.setPlainText("unsaved needle")
        dialog = self.dialog()
        dialog.query.setText("unsaved needle")
        self.assertEqual(dialog.table.rowCount(), 1)
        dialog.open_selected()
        self.assertTrue(self.window.dirty)
        self.assertEqual(self.window.replace_edit.toPlainText(), "unsaved needle")
        self.assertEqual(ConfigService.parse_yaml(self.first)[0].replace, "original")

    def test_cancel_and_save_when_opening_another_file(self):
        self.window.load_file(self.first)
        self.window.replace_edit.setPlainText("save this")
        dialog = self.dialog()
        dialog.query.setText(":alias")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
            dialog.open_selected()
        self.assertEqual(self.window.current_file, self.first)
        self.assertTrue(self.window.dirty)
        self.assertEqual(dialog.result(), 0)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.open_selected()
        self.assertEqual(self.window.current_file, self.second)
        self.assertEqual(ConfigService.parse_yaml(self.first)[0].replace, "save this")

    def test_bad_yaml_does_not_hide_valid_results(self):
        (self.directory / "broken.yml").write_text("matches: [", encoding="utf-8")
        (self.directory / "binary.yml").write_bytes(b"\xff")
        dialog = self.dialog()
        dialog.query.setText(":alias")
        self.assertEqual(dialog.table.rowCount(), 1)
        self.assertTrue(any("Skipped 2" in label.text() for label in dialog.findChildren(QLabel)))

    def test_failed_save_keeps_current_edits_and_search_open(self):
        self.window.load_file(self.first)
        self.window.replace_edit.setPlainText("keep this")
        dialog = self.dialog()
        dialog.query.setText(":alias")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
                patch.object(ConfigService, "save_yaml", side_effect=OSError("read-only")), \
                patch.object(QMessageBox, "critical") as error:
            dialog.open_selected()
        error.assert_called_once()
        self.assertEqual(self.window.current_file, self.first)
        self.assertEqual(self.window.replace_edit.toPlainText(), "keep this")
        self.assertTrue(self.window.dirty)
        self.assertEqual(dialog.result(), 0)

    def test_discard_changes_when_opening_another_file(self):
        self.window.load_file(self.first)
        self.window.replace_edit.setPlainText("discard this")
        dialog = self.dialog()
        dialog.query.setText(":alias")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            dialog.open_selected()
        self.assertEqual(self.window.current_file, self.second)
        self.assertFalse(self.window.dirty)
        self.assertEqual(ConfigService.parse_yaml(self.first)[0].replace, "original")

    def test_deleted_result_reports_error_without_losing_edits(self):
        self.window.load_file(self.first)
        dialog = self.dialog()
        dialog.query.setText(":alias")
        self.second.unlink()
        with patch.object(QMessageBox, "critical") as error:
            dialog.open_selected()
        error.assert_called_once()
        self.assertEqual(self.window.current_file, self.first)
        self.assertEqual(dialog.result(), 0)

    def test_local_filter_searches_beyond_preview(self):
        self.window.load_file(self.second)
        self.window.match_filter.setText("STRASSE")
        self.assertEqual(self.window.match_table.rowCount(), 1)


if __name__ == "__main__":
    unittest.main()
