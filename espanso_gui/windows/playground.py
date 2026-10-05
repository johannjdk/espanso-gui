"""Interactive match playground for testing text expansion live."""

from __future__ import annotations

import datetime
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import EspansoMatch


class PlaygroundHeader(QFrame):
    def __init__(self, toggle_callback) -> None:
        super().__init__()
        self.toggle_callback = toggle_callback
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        self.title_label = QLabel("Match Playground")
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setToolTip("Clear playground text")
        self.clear_btn.hide()
        layout.addWidget(self.clear_btn)

        self.toggle_btn = QPushButton("Open")
        self.toggle_btn.clicked.connect(self.toggle_callback)
        layout.addWidget(self.toggle_btn)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            if not self.toggle_btn.geometry().contains(pos) and not self.clear_btn.geometry().contains(pos):
                self.toggle_callback()
        super().mousePressEvent(event)

    def set_open(self, is_open: bool) -> None:
        self.toggle_btn.setText("Close" if is_open else "Open")
        self.clear_btn.setVisible(is_open)
        self.setCursor(Qt.CursorShape.ArrowCursor if is_open else Qt.CursorShape.PointingHandCursor)


class PlaygroundMixin:
    def _build_playground_panel(self) -> QWidget:
        self._playground_open = False
        self._playground_height = 180
        self._expanding = False

        self.playground_panel = QFrame()
        self.playground_panel.setFrameShape(QFrame.Shape.StyledPanel)
        panel_layout = QVBoxLayout(self.playground_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        self.playground_header = PlaygroundHeader(lambda *args: self.toggle_playground())
        self.playground_header.clear_btn.clicked.connect(self.clear_playground)
        self.playground_status = self.playground_header.status_label
        panel_layout.addWidget(self.playground_header)

        self.playground_content = QWidget()
        content_layout = QVBoxLayout(self.playground_content)
        content_layout.setContentsMargins(8, 0, 8, 6)
        content_layout.setSpacing(2)

        self.playground_edit = QPlainTextEdit()
        self.playground_edit.setPlaceholderText("Test triggers here")
        self.playground_edit.textChanged.connect(self._on_playground_text_changed)
        content_layout.addWidget(self.playground_edit)

        self.playground_content.hide()
        panel_layout.addWidget(self.playground_content)

        header_height = self.playground_header.sizeHint().height() + 2
        self.playground_panel.setMaximumHeight(header_height)

        return self.playground_panel

    def toggle_playground(self, *args, show: bool | None = None) -> None:
        if show is None:
            show = not getattr(self, "_playground_open", False)
        self._playground_open = show

        self.playground_content.setVisible(show)
        self.playground_header.set_open(show)

        handle = self.vertical_splitter.handle(1)
        if show:
            self.playground_panel.setMaximumHeight(16777215)
            if handle:
                handle.setEnabled(True)
                handle.setCursor(Qt.CursorShape.SplitVCursor)
            target_h = getattr(self, "_playground_height", 180)
            total = self.vertical_splitter.height()
            top_h = max(150, total - target_h)
            self.vertical_splitter.setSizes([top_h, target_h])
            self.playground_edit.setFocus()
        else:
            sizes = self.vertical_splitter.sizes()
            if len(sizes) > 1 and sizes[1] > 60:
                self._playground_height = sizes[1]
            header_height = self.playground_header.sizeHint().height() + 2
            self.playground_panel.setMaximumHeight(header_height)
            if handle:
                handle.setEnabled(False)
                handle.setCursor(Qt.CursorShape.ArrowCursor)
            total = self.vertical_splitter.height()
            self.vertical_splitter.setSizes([max(150, total - header_height), header_height])

    def clear_playground(self) -> None:
        self.playground_edit.clear()
        self.playground_status.clear()
        self.playground_edit.setFocus()

    def _on_playground_text_changed(self) -> None:
        if getattr(self, "_expanding", False):
            return

        cursor = self.playground_edit.textCursor()
        pos = cursor.position()
        text = self.playground_edit.toPlainText()[:pos]
        if not text:
            return

        if hasattr(self, "persist_current_match"):
            self.persist_current_match()

        best_match: EspansoMatch | None = None
        best_len = 0
        best_trigger = ""
        best_groups: dict[str, str] = {}

        for match in self.matches:
            matched_len = 0
            matched_trigger = ""
            named_groups: dict[str, str] = {}

            if match.regex:
                try:
                    pattern = rf"(?:^|\b|\s)({match.regex})$" if match.word else rf"({match.regex})$"
                    m = re.search(pattern, text)
                except re.error:
                    m = None
                if m is not None:
                    matched_trigger = m.group(1)
                    matched_len = len(matched_trigger)
                    named_groups = {k: v for k, v in m.groupdict().items() if v is not None}
            else:
                triggers = match.triggers if match.triggers else ([match.trigger] if match.trigger else [])
                for trigger in triggers:
                    if not trigger or not text.endswith(trigger):
                        continue
                    if match.word:
                        prefix_len = len(text) - len(trigger)
                        if prefix_len > 0 and text[prefix_len - 1].isalnum():
                            continue
                    matched_trigger = trigger
                    matched_len = len(trigger)
                    break

            if matched_len > best_len:
                best_match = match
                best_len = matched_len
                best_trigger = matched_trigger
                best_groups = named_groups

        if best_match is None or best_len == 0:
            return

        replacement = best_match.form if best_match.is_form else best_match.replace

        for group_name, group_val in best_groups.items():
            replacement = replacement.replace(f"{{{{{group_name}}}}}", group_val)

        replacement = self._evaluate_playground_variables(best_match, replacement)
        if best_match.is_form:
            replacement = self._evaluate_playground_form_fields(best_match, replacement)

        cursor_offset = None
        if "$|$" in replacement:
            cursor_offset = replacement.index("$|$")
            replacement = replacement.replace("$|$", "")

        self._expanding = True
        cursor.beginEditBlock()
        cursor.setPosition(pos - best_len, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(replacement)
        if cursor_offset is not None:
            cursor.setPosition(pos - best_len + cursor_offset)
            self.playground_edit.setTextCursor(cursor)
        cursor.endEditBlock()
        self._expanding = False

        preview = replacement.replace("\n", " ↵ ")
        if len(preview) > 50:
            preview = preview[:50] + "…"
        self.playground_status.setText(f"Expanded: {best_trigger} → {preview}")
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage(f"Playground: expanded {best_trigger}", 3000)

    def _evaluate_playground_variables(self, match: EspansoMatch, text: str) -> str:
        for var in match.variables:
            placeholder = f"{{{{{var.name}}}}}"
            if placeholder not in text:
                continue
            val = ""
            if var.type == "date":
                fmt = var.params.get("format", "%x")
                try:
                    val = datetime.datetime.now().strftime(str(fmt))
                except Exception:
                    val = str(fmt)
            elif var.type == "choice":
                choices = var.params.get("choices") or var.params.get("values") or []
                val = str(choices[0]) if choices else ""
            elif var.type == "echo":
                val = str(var.params.get("echo", ""))
            elif var.type == "clipboard":
                val = QApplication.clipboard().text()
            if val:
                text = text.replace(placeholder, val)
        return text

    def _evaluate_playground_form_fields(self, match: EspansoMatch, text: str) -> str:
        for name, field_obj in match.form_fields.items():
            val = field_obj.default or (field_obj.values[0] if field_obj.values else f"[{name}]")
            text = re.sub(rf"\[\[\s*{re.escape(name)}\s*\]\]", val, text)
        return text
