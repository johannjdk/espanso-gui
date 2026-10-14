"""YAML editor widget and syntax highlighter."""

from __future__ import annotations

import yaml
from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QPalette,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import QApplication, QMessageBox, QPlainTextEdit, QTextEdit, QWidget

from ..config_service import ConfigService
from .code_editor import CodeEditor
from .fonts import mono_font


class YamlHighlighter(QSyntaxHighlighter):
    def __init__(self, parent: QTextDocument | QPlainTextEdit | QTextEdit | None = None) -> None:
        target_doc = parent.document() if isinstance(parent, QPlainTextEdit) else parent
        super().__init__(target_doc)
        self._widget = parent if isinstance(parent, QWidget) else None
        self._is_dark: bool | None = None
        self._rules: list[tuple[QRegularExpression, int, QTextCharFormat]] = []
        self._str_re = QRegularExpression(r'"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\'')
        self._comment_re = QRegularExpression(r"(?:^|\s)(#.*)$")
        self._comment_fmt = QTextCharFormat()
        self._str_fmt = QTextCharFormat()
        self._update_theme()

    def _update_theme(self) -> None:
        palette = self._widget.palette() if self._widget is not None else QApplication.palette()
        is_dark = palette.color(QPalette.ColorRole.Base).lightness() < 128
        if is_dark == self._is_dark:
            return
        self._is_dark = is_dark

        if is_dark:
            key_color = QColor("#79c0ff")
            str_color = QColor("#7ee787")
            num_color = QColor("#ffa657")
            bool_color = QColor("#d2a8ff")
            comment_color = QColor("#8b949e")
            dash_color = QColor("#c9d1d9")
        else:
            key_color = QColor("#0550ae")
            str_color = QColor("#0a7a3b")
            num_color = QColor("#b35900")
            bool_color = QColor("#8250df")
            comment_color = QColor("#6e7781")
            dash_color = QColor("#24292e")

        key_fmt = QTextCharFormat()
        key_fmt.setForeground(key_color)
        key_fmt.setFontWeight(QFont.Weight.Bold)

        dash_fmt = QTextCharFormat()
        dash_fmt.setForeground(dash_color)
        dash_fmt.setFontWeight(QFont.Weight.Bold)

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(num_color)

        bool_fmt = QTextCharFormat()
        bool_fmt.setForeground(bool_color)

        self._str_fmt = QTextCharFormat()
        self._str_fmt.setForeground(str_color)

        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(comment_color)
        self._comment_fmt.setFontItalic(True)

        self._rules = [
            (QRegularExpression(r"^\s*(?:-\s+)?(\"[^\"]+\"|'[^']+'|[\w.-]+)(?=\s*:)"), 1, key_fmt),
            (QRegularExpression(r"^\s*(-)\s"), 1, dash_fmt),
            (QRegularExpression(r"(?<=[:\s\[{,])[-+]?(?:0x[0-9a-fA-F]+|\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)(?=[\s,\]}]|$)"), 0, num_fmt),
            (QRegularExpression(r"(?<=[:\s\[{,])(true|false|yes|no|on|off|null|~)(?=[\s,\]}]|$)", QRegularExpression.PatternOption.CaseInsensitiveOption), 0, bool_fmt),
            (QRegularExpression(r"(?<=[:\s])(\||\>)[+-]?(?=\s|$)"), 0, dash_fmt),
            (QRegularExpression(r"(&|\*)[A-Za-z0-9_-]+"), 0, bool_fmt),
            (QRegularExpression(r"^(?:---|\\.\\.\\.)\s*$"), 0, dash_fmt),
        ]

    def highlightBlock(self, text: str) -> None:
        self._update_theme()

        for pattern, group, fmt in self._rules:
            match_it = pattern.globalMatch(text)
            while match_it.hasNext():
                match = match_it.next()
                self.setFormat(match.capturedStart(group), match.capturedLength(group), fmt)

        str_spans: list[tuple[int, int]] = []
        str_it = self._str_re.globalMatch(text)
        while str_it.hasNext():
            match = str_it.next()
            start, length = match.capturedStart(0), match.capturedLength(0)
            self.setFormat(start, length, self._str_fmt)
            str_spans.append((start, start + length))

        comment_it = self._comment_re.globalMatch(text)
        while comment_it.hasNext():
            match = comment_it.next()
            start = match.capturedStart(1)
            if not any(s <= start < e for s, e in str_spans):
                self.setFormat(start, len(text) - start, self._comment_fmt)
                break


class YamlEditor(CodeEditor):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFont(mono_font(10))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 2)
        self.set_line_numbers_visible(ConfigService.get_show_line_numbers())
        self.highlighter = YamlHighlighter(self)

    def format_yaml(self) -> bool:
        try:
            formatted = ConfigService.format_yaml_text(self.toPlainText())
            if formatted != self.toPlainText():
                pos = self.textCursor().position()
                self.setPlainText(formatted)
                cursor = self.textCursor()
                cursor.setPosition(min(pos, len(formatted)))
                self.setTextCursor(cursor)
            return True
        except (ValueError, yaml.YAMLError) as error:
            QMessageBox.warning(self, "Invalid YAML", str(error))
            return False

    def contextMenuEvent(self, event) -> None:
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        format_action = menu.addAction("Format YAML")
        format_action.setShortcut("Ctrl+Shift+F")
        format_action.triggered.connect(self.format_yaml)
        menu.exec(event.globalPos())

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Tab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                self._indent_selection(forward=True)
            else:
                cursor.insertText("  ")
            return

        if event.key() == Qt.Key.Key_Backtab:
            self._indent_selection(forward=False)
            return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            line = cursor.block().text()
            indent = " " * (len(line) - len(line.lstrip(" ")))
            if line.rstrip().endswith(":"):
                indent += "  "
            cursor.insertText("\n" + indent)
            return

        super().keyPressEvent(event)

    def _indent_selection(self, forward: bool) -> None:
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)

        cursor.beginEditBlock()
        while cursor.position() <= end:
            if forward:
                cursor.insertText("  ")
                end += 2
            else:
                line = cursor.block().text()
                if line.startswith("  "):
                    cursor.deleteChar()
                    cursor.deleteChar()
                    end = max(start, end - 2)
                elif line.startswith(" "):
                    cursor.deleteChar()
                    end = max(start, end - 1)
            if not cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                break
        cursor.endEditBlock()

