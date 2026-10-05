"""Simple match playground text field for testing triggers."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PlaygroundMixin:
    def _build_playground_panel(self) -> QWidget:
        self._playground_open = False
        self._playground_height = 140

        self.playground_panel = QFrame()
        self.playground_panel.setFrameShape(QFrame.Shape.StyledPanel)
        panel_layout = QVBoxLayout(self.playground_panel)
        panel_layout.setContentsMargins(10, 4, 10, 4)
        panel_layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.playground_title = QLabel("Playground")
        header_layout.addWidget(self.playground_title)
        header_layout.addStretch()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_playground)
        self.clear_btn.hide()
        header_layout.addWidget(self.clear_btn)

        self.toggle_btn = QPushButton("Open")
        self.toggle_btn.clicked.connect(lambda: self.toggle_playground())
        header_layout.addWidget(self.toggle_btn)

        panel_layout.addLayout(header_layout)

        self.playground_edit = QPlainTextEdit()
        self.playground_edit.setPlaceholderText("Type triggers here to test…")
        self.playground_edit.hide()
        panel_layout.addWidget(self.playground_edit)

        # Collapsed by default
        collapsed_h = self.playground_panel.sizeHint().height() + 2
        self.playground_panel.setMaximumHeight(collapsed_h)

        # Backward compatibility references
        self.playground_header = self.playground_panel
        self.playground_status = QLabel()

        return self.playground_panel

    def toggle_playground(self, *args, show: bool | None = None) -> None:
        if show is None:
            show = not getattr(self, "_playground_open", False)
        self._playground_open = show

        handle = self.vertical_splitter.handle(1)
        if show:
            self.playground_panel.setMaximumHeight(16777215)
            self.playground_edit.show()
            self.clear_btn.show()
            self.toggle_btn.setText("Close")
            if handle:
                handle.setEnabled(True)
                handle.setCursor(Qt.CursorShape.SplitVCursor)

            target_h = getattr(self, "_playground_height", 140)
            total = self.vertical_splitter.height()
            top_h = max(200, total - target_h)
            self.vertical_splitter.setSizes([top_h, target_h])
            self.playground_edit.setFocus()
        else:
            sizes = self.vertical_splitter.sizes()
            if len(sizes) == 2 and sizes[1] > 60:
                self._playground_height = sizes[1]

            self.playground_edit.hide()
            self.clear_btn.hide()
            self.toggle_btn.setText("Open")

            collapsed_h = self.playground_title.sizeHint().height() + 16
            self.playground_panel.setMaximumHeight(collapsed_h)
            if handle:
                handle.setEnabled(False)
                handle.setCursor(Qt.CursorShape.ArrowCursor)

            total = self.vertical_splitter.height()
            self.vertical_splitter.setSizes([max(200, total - collapsed_h), collapsed_h])

    def clear_playground(self) -> None:
        self.playground_edit.clear()
        self.playground_edit.setFocus()
