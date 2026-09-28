"""Regression coverage for stale content in the match editor (issue #1)."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from espanso_gui.app import MainWindow
from espanso_gui.models import EspansoMatch


class MatchEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Do not load or modify the user's Espanso configuration.
        with patch.object(MainWindow, "load_files"):
            self.window = MainWindow()
        self.window.matches = [
            EspansoMatch(trigger=":text", replace="Existing text"),
            EspansoMatch(trigger=":form", mode="form", form="Hello [[name]]"),
        ]
        self.window.refresh_match_table()

    def tearDown(self):
        self.window.deleteLater()
        self.app.processEvents()

    def test_selection_refreshes_both_editors_without_changing_content(self):
        window = self.window
        for index in (0, 1, 0, 1):
            window._select_match(index)
            match = window.matches[index]
            self.assertEqual(window.replace_edit.toPlainText(), match.replace)
            self.assertEqual(window.form_layout_edit.toPlainText(), match.form)
        self.assertEqual(window.matches[0].replace, "Existing text")
        self.assertEqual(window.matches[1].form, "Hello [[name]]")
        self.assertFalse(window.dirty)

    def test_new_match_has_no_content_from_previous_match(self):
        window = self.window
        for index in (0, 1):
            window._select_match(index)
            window.new_match()
            self.assertEqual(window.selected_match, len(window.matches) - 1)
            self.assertEqual(window.replace_edit.toPlainText(), "")
            self.assertEqual(window.form_layout_edit.toPlainText(), "")
            window.radio_form.setChecked(True)
            self.assertEqual(window.form_layout_edit.toPlainText(), "")
            self.assertEqual(window.matches[-1].to_yaml(), {"trigger": ":new", "form": ""})

    def test_mode_switch_clears_content_and_updates_serialized_type(self):
        window = self.window
        window._select_match(0)
        window.radio_form.setChecked(True)
        self.assertEqual(window.form_layout_edit.toPlainText(), "")
        self.assertEqual(window.matches[0].to_yaml(), {"trigger": ":text", "form": ""})
        window.form_layout_edit.setPlainText("New [[field]]")
        window.radio_replace.setChecked(True)
        self.assertEqual(window.replace_edit.toPlainText(), "")
        self.assertEqual(window.form_layout_edit.toPlainText(), "")
        self.assertEqual(window.matches[0].to_yaml(), {"trigger": ":text", "replace": ""})
        self.assertTrue(window.dirty)


if __name__ == "__main__":
    unittest.main()
