"""Main window menus and selection-dependent actions."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QLineEdit, QMenu, QPlainTextEdit, QTextEdit

from ..ui.about_dialog import show_about_dialog


class MenuMixin:
    def _menu_action(
        self, menu: QMenu, title: str, callback: Callable[..., object],
        shortcut: str | QKeySequence.StandardKey | None = None,
    ) -> QAction:
        action = QAction(title, self)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(callback)
        menu.addAction(action)
        return action

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        self._menu_action(file_menu, "New configuration…", self.new_file, "Ctrl+N")
        self.save_action = self._menu_action(file_menu, "Save", self.save_current_file, "Ctrl+S")
        self.delete_config_action = self._menu_action(file_menu, "Delete configuration…", self.delete_file)
        file_menu.addSeparator()
        self.yaml_action = self._menu_action(file_menu, "Expert YAML…", self.open_yaml_editor, "Ctrl+E")
        self._menu_action(file_menu, "Espanso configuration…", self.open_espanso_configuration)
        self._menu_action(file_menu, "Espanso GUI Configuration", self.open_espanso_gui_configuration)
        file_menu.addSeparator()
        self._menu_action(file_menu, "Quit", self.close, "Ctrl+Q")

        edit_menu = self.menuBar().addMenu("Edit")
        self.text_actions = {}
        for title, method, shortcut in (
            ("Undo", "undo", QKeySequence.StandardKey.Undo),
            ("Redo", "redo", QKeySequence.StandardKey.Redo),
            ("Cut", "cut", QKeySequence.StandardKey.Cut),
            ("Copy", "copy", QKeySequence.StandardKey.Copy),
            ("Paste", "paste", QKeySequence.StandardKey.Paste),
            ("Select all", "selectAll", QKeySequence.StandardKey.SelectAll),
        ):
            if method in ("cut", "selectAll"):
                edit_menu.addSeparator()
            self.text_actions[method] = self._menu_action(
                edit_menu, title, lambda checked=False, method=method: self._edit_text(method), shortcut
            )
        edit_menu.addSeparator()
        self.new_match_action = self._menu_action(edit_menu, "New match", self.new_match, "Ctrl+Shift+N")
        self.match_actions = [
            self._menu_action(edit_menu, "Duplicate match", self.duplicate_match, "Ctrl+D"),
            self._menu_action(edit_menu, "Move match…", self.move_match, "Ctrl+Shift+M"),
            self._menu_action(edit_menu, "Delete match…", self.delete_match, "Ctrl+Shift+Delete"),
        ]

        search_menu = self.menuBar().addMenu("Search")
        self._menu_action(search_menu, "Search all configurations…", self.search_all_configurations, "Ctrl+F")
        self.filter_action = self._menu_action(
            search_menu, "Filter current file", self._focus_match_filter, "Ctrl+L"
        )

        tools_menu = self.menuBar().addMenu("Tools")
        self._menu_action(tools_menu, "Match playground", self.toggle_playground, "Ctrl+P")
        self._menu_action(tools_menu, "Statistics…", self.open_statistics)
        self._menu_action(tools_menu, "Restart Espanso", self.restart_espanso, "Ctrl+Shift+R")

        help_menu = self.menuBar().addMenu("Help")
        self._menu_action(
            help_menu,
            "About Espanso GUI",
            lambda: show_about_dialog(self, self.config_path, getattr(self, "espanso_version", None)),
        )
        for menu in (file_menu, edit_menu, search_menu):
            menu.aboutToShow.connect(self._update_menu_actions)
        self.file_tree.itemSelectionChanged.connect(self._update_menu_actions)
        self.match_table.itemSelectionChanged.connect(self._update_menu_actions)
        QApplication.instance().focusChanged.connect(self._update_menu_actions)
        QApplication.clipboard().dataChanged.connect(self._update_menu_actions)
        self._update_menu_actions()

    def _text_editor(self) -> QLineEdit | QTextEdit | QPlainTextEdit | None:
        widget = QApplication.focusWidget()
        if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit)) and widget.window() is self:
            return widget
        return None

    def _edit_text(self, method: str) -> None:
        editor = self._text_editor()
        if editor is not None and editor.isEnabled():
            getattr(editor, method)()
            self._update_menu_actions()

    def _focus_match_filter(self) -> None:
        self.match_filter.setFocus()
        self.match_filter.selectAll()

    def _update_menu_actions(self, *_args) -> None:
        has_file = self.current_file is not None and self.match_sidebar.isEnabled()
        self.save_action.setEnabled(has_file)
        self.yaml_action.setEnabled(has_file)
        self.new_match_action.setEnabled(has_file)
        self.filter_action.setEnabled(has_file)
        files = self.file_tree.selectedItems()
        self.delete_config_action.setEnabled(
            bool(files) and isinstance(files[0].data(0, Qt.ItemDataRole.UserRole), Path)
        )
        has_match = has_file and 0 <= self.selected_match < len(self.matches)
        rows = self.match_table.selectionModel().selectedRows()
        has_match = has_match and any(
            self.match_table.item(row.row(), 0).data(Qt.ItemDataRole.UserRole) == self.selected_match
            for row in rows
        )
        for action in self.match_actions:
            action.setEnabled(has_match)
        self.duplicate_match_btn.setEnabled(has_match)
        self.move_match_btn.setEnabled(has_match)
        self.delete_match_btn.setEnabled(has_match)

        editor = self._text_editor()
        enabled = {method: False for method in self.text_actions}
        if editor is not None and editor.isEnabled():
            writable = not editor.isReadOnly()
            if isinstance(editor, QLineEdit):
                selected = editor.hasSelectedText()
                has_text = bool(editor.text())
                undo, redo = editor.isUndoAvailable(), editor.isRedoAvailable()
            else:
                selected = editor.textCursor().hasSelection()
                has_text = not editor.document().isEmpty()
                undo, redo = editor.document().isUndoAvailable(), editor.document().isRedoAvailable()
            enabled.update(
                undo=writable and undo, redo=writable and redo,
                cut=writable and selected, copy=selected,
                paste=writable and bool(QApplication.clipboard().text()), selectAll=has_text,
            )
        for method, action in self.text_actions.items():
            action.setEnabled(enabled[method])
