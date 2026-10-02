import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from espanso_gui.config_service import ConfigService
from espanso_gui.models import EspansoMatch
from espanso_gui.windows.main_window import MainWindow


class MenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.path = self.directory / "base.yml"
        ConfigService.save_yaml(self.path, [EspansoMatch(trigger=":hello", replace="Hello")])
        with patch.object(ConfigService, "detect_config_path", return_value=self.directory):
            self.window = MainWindow()
        self.window.show()
        self.window.activateWindow()
        self.app.processEvents()
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        self.window.dirty = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def menu(self, title):
        return next(action.menu() for action in self.window.menuBar().actions() if action.text() == title)

    def action(self, menu, title):
        return next(action for action in self.menu(menu).actions() if action.text() == title)

    def test_actions_follow_file_and_match_selection(self):
        self.assertFalse(self.window.save_action.isEnabled())
        self.assertFalse(self.window.new_match_action.isEnabled())
        self.assertFalse(any(action.isEnabled() for action in self.window.match_actions))
        self.assertTrue(self.action("Search", "Search all configurations…").isEnabled())
        self.assertTrue(self.action("Tools", "Restart Espanso").isEnabled())
        self.window.load_file(self.path)
        self.assertTrue(self.window.save_action.isEnabled())
        self.assertTrue(self.window.new_match_action.isEnabled())
        self.assertTrue(all(action.isEnabled() for action in self.window.match_actions))
        self.window.match_filter.setText("no results")
        self.assertFalse(any(action.isEnabled() for action in self.window.match_actions))
        self.assertFalse(self.window.delete_match_btn.isEnabled())
        empty = self.directory / "empty.yml"
        ConfigService.save_yaml(empty, [])
        self.window.load_file(empty)
        self.assertTrue(self.window.new_match_action.isEnabled())
        self.assertFalse(any(action.isEnabled() for action in self.window.match_actions))

    def test_new_match_shortcut_clears_filter_and_selects_created_match(self):
        self.window.load_file(self.path)
        self.window.match_filter.setText("no results")
        self.window.match_filter.setFocus()
        QTest.keyClick(self.window.match_filter, Qt.Key.Key_N,
                       Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(len(self.window.matches), 2)
        self.assertEqual(self.window.trigger_edit.text(), ":new")
        self.assertEqual(self.window.selected_match, 1)
        self.assertTrue(all(action.isEnabled() for action in self.window.match_actions))

    def test_delete_text_does_not_delete_match(self):
        self.window.load_file(self.path)
        self.window.trigger_edit.setFocus()
        self.window.trigger_edit.selectAll()
        with patch.object(QMessageBox, "question") as question:
            QTest.keyClick(self.window.trigger_edit, Qt.Key.Key_Delete)
        question.assert_not_called()
        self.assertEqual(len(self.window.matches), 1)
        self.assertEqual(self.window.trigger_edit.text(), "")

    def test_delete_match_still_requires_confirmation(self):
        self.window.load_file(self.path)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            self.action("Edit", "Delete match…").trigger()
        self.assertEqual(len(self.window.matches), 1)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.action("Edit", "Delete match…").trigger()
        self.assertEqual(self.window.matches, [])
        self.assertFalse(any(action.isEnabled() for action in self.window.match_actions))

    def test_text_menu_uses_focused_editor_and_supports_undo(self):
        self.window.load_file(self.path)
        editor = self.window.replace_edit
        editor.setFocus()
        editor.selectAll()
        QTest.keyClicks(editor, "Changed")
        menu = self.menu("Edit")
        menu.popup(self.window.mapToGlobal(QPoint(20, 40)))
        self.app.processEvents()
        undo = self.action("Edit", "Undo")
        self.assertTrue(undo.isEnabled())
        QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(undo).center())
        self.assertEqual(editor.toPlainText(), "Hello")
        menu.aboutToShow.emit()
        self.action("Edit", "Redo").trigger()
        self.assertEqual(editor.toPlainText(), "Changed")
        editor.selectAll()
        menu.aboutToShow.emit()
        self.action("Edit", "Copy").trigger()
        self.assertEqual(QApplication.clipboard().text(), "Changed")
        self.window.trigger_edit.setFocus()
        self.window.trigger_edit.selectAll()
        menu.aboutToShow.emit()
        self.action("Edit", "Paste").trigger()
        self.assertEqual(self.window.trigger_edit.text(), "Changed")
        self.assertEqual(editor.toPlainText(), "Changed")

    def test_read_only_text_cannot_be_changed_from_menu(self):
        self.window.load_file(self.path)
        self.window.replace_edit.setFocus()
        self.window.replace_edit.selectAll()
        self.window.replace_edit.setReadOnly(True)
        self.menu("Edit").aboutToShow.emit()
        self.assertTrue(self.action("Edit", "Copy").isEnabled())
        for title in ("Cut", "Paste", "Undo", "Redo"):
            self.assertFalse(self.action("Edit", title).isEnabled())

    def test_quit_keeps_unsaved_changes_when_cancelled(self):
        self.window.load_file(self.path)
        self.window.replace_edit.setPlainText("unsaved")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
            self.action("File", "Quit").trigger()
        self.assertTrue(self.window.isVisible())
        self.assertTrue(self.window.dirty)
        self.assertEqual(self.window.replace_edit.toPlainText(), "unsaved")


if __name__ == "__main__":
    unittest.main()
