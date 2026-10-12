"""Syntax highlighter for Espanso template replacement and form fields."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import (
    QColor,
    QFont,
    QPalette,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QTextEdit, QWidget


class TemplateHighlighter(QSyntaxHighlighter):
    def __init__(self, parent: QTextDocument | QPlainTextEdit | QTextEdit | None = None) -> None:
        target_doc = parent.document() if isinstance(parent, (QPlainTextEdit, QTextEdit)) else parent
        super().__init__(target_doc)
        self._widget = parent if isinstance(parent, QWidget) else None
        self._is_dark: bool | None = None
        self._var_re = QRegularExpression(r"\{\{\s*[\$\w.-]+\s*\}\}")
        self._form_re = QRegularExpression(r"\[\[\s*[\$\w.-]+\s*\]\]")
        self._backref_re = QRegularExpression(r"\$[0-9]+|\$<[\w]+>")
        self._var_fmt = QTextCharFormat()
        self._form_fmt = QTextCharFormat()
        self._update_theme()

    def _update_theme(self) -> None:
        palette = self._widget.palette() if self._widget is not None else QApplication.palette()
        is_dark = palette.color(QPalette.ColorRole.Base).lightness() < 128
        if is_dark == self._is_dark:
            return
        self._is_dark = is_dark

        if is_dark:
            var_fg = QColor("#d2a8ff")
            var_bg = QColor(210, 168, 255, 32)
            form_fg = QColor("#79c0ff")
            form_bg = QColor(121, 192, 255, 32)
        else:
            var_fg = QColor("#6f42c1")
            var_bg = QColor(111, 66, 193, 24)
            form_fg = QColor("#0969da")
            form_bg = QColor(9, 105, 218, 24)

        self._var_fmt = QTextCharFormat()
        self._var_fmt.setForeground(var_fg)
        self._var_fmt.setBackground(var_bg)
        self._var_fmt.setFontWeight(QFont.Weight.Bold)

        self._form_fmt = QTextCharFormat()
        self._form_fmt.setForeground(form_fg)
        self._form_fmt.setBackground(form_bg)
        self._form_fmt.setFontWeight(QFont.Weight.Bold)

    def highlightBlock(self, text: str) -> None:
        self._update_theme()

        for pattern, fmt in (
            (self._var_re, self._var_fmt),
            (self._backref_re, self._var_fmt),
            (self._form_re, self._form_fmt),
        ):
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(0), match.capturedLength(0), fmt)
