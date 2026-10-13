"""Syntax highlighter for Bash / Shell scripts."""

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


class BashHighlighter(QSyntaxHighlighter):
    """Simple syntax highlighter for Bash commands and shell scripts."""

    def __init__(self, parent: QTextDocument | QPlainTextEdit | QTextEdit | None = None) -> None:
        target_doc = parent.document() if isinstance(parent, (QPlainTextEdit, QTextEdit)) else parent
        super().__init__(target_doc)
        self._widget = parent if isinstance(parent, QWidget) else None
        self._is_dark: bool | None = None

        self._keywords = [
            "if", "then", "else", "elif", "fi", "case", "esac", "for", "select",
            "while", "until", "do", "done", "in", "function", "time", "eval",
            "exec", "exit", "export", "read", "return", "set", "shift", "source",
            "trap", "unset", "echo", "printf", "local", "alias", "test"
        ]
        kw_pattern = r"\b(?:" + "|".join(self._keywords) + r")\b"
        self._keyword_re = QRegularExpression(kw_pattern)
        self._comment_re = QRegularExpression(r"(?:^|\s)(#.*)$")
        self._str_double_re = QRegularExpression(r'"[^"\\]*(?:\\.[^"\\]*)*"')
        self._str_single_re = QRegularExpression(r"'[^'\\]*(?:\\.[^'\\]*)*'")
        self._variable_re = QRegularExpression(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|\$[0-9?*@#$!-]")
        self._pipe_op_re = QRegularExpression(r"[|&;><]+")

        self._kw_fmt = QTextCharFormat()
        self._comment_fmt = QTextCharFormat()
        self._str_fmt = QTextCharFormat()
        self._var_fmt = QTextCharFormat()
        self._op_fmt = QTextCharFormat()

        self._update_theme()

    def _update_theme(self) -> None:
        palette = self._widget.palette() if self._widget is not None else QApplication.palette()
        is_dark = palette.color(QPalette.ColorRole.Base).lightness() < 128
        if is_dark == self._is_dark:
            return
        self._is_dark = is_dark

        if is_dark:
            kw_color = QColor("#ff7b72")
            str_color = QColor("#a5d6ff")
            var_color = QColor("#ffa657")
            comment_color = QColor("#8b949e")
            op_color = QColor("#79c0ff")
        else:
            kw_color = QColor("#cf222e")
            str_color = QColor("#0a7a3b")
            var_color = QColor("#953800")
            comment_color = QColor("#6e7781")
            op_color = QColor("#0550ae")

        self._kw_fmt = QTextCharFormat()
        self._kw_fmt.setForeground(kw_color)
        self._kw_fmt.setFontWeight(QFont.Weight.Bold)

        self._str_fmt = QTextCharFormat()
        self._str_fmt.setForeground(str_color)

        self._var_fmt = QTextCharFormat()
        self._var_fmt.setForeground(var_color)
        self._var_fmt.setFontWeight(QFont.Weight.Bold)

        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(comment_color)
        self._comment_fmt.setFontItalic(True)

        self._op_fmt = QTextCharFormat()
        self._op_fmt.setForeground(op_color)

    def highlightBlock(self, text: str) -> None:
        self._update_theme()

        # Keywords
        it = self._keyword_re.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self._kw_fmt)

        # Operators
        it = self._pipe_op_re.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self._op_fmt)

        # Variables ($VAR, ${VAR}, $1, etc.)
        it = self._variable_re.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self._var_fmt)

        # Strings double quotes
        it = self._str_double_re.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self._str_fmt)

        # Strings single quotes
        it = self._str_single_re.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self._str_fmt)

        # Comments
        it = self._comment_re.globalMatch(text)
        while it.hasNext():
            match = it.next()
            # capture group 1 starts at match.capturedStart(1)
            start = match.capturedStart(1)
            length = match.capturedLength(1)
            self.setFormat(start, length, self._comment_fmt)

