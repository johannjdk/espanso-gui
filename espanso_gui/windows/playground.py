"""Simple match playground text field for testing triggers."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PlaygroundMixin:
    def _build_playground_panel(self) -> QWidget:
        self.playground_panel = QWidget()
        panel_layout = QVBoxLayout(self.playground_panel)
        panel_layout.setContentsMargins(10, 6, 10, 8)
        panel_layout.setSpacing(6)

        header_layout = QHBoxLayout()
        self.playground_title = QLabel("Playground")
        header_layout.addWidget(self.playground_title)
        header_layout.addStretch()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_playground)
        header_layout.addWidget(self.clear_btn)

        self.hide_btn = QPushButton("Hide")
        self.hide_btn.clicked.connect(lambda: self.toggle_playground(show=False))
        header_layout.addWidget(self.hide_btn)

        panel_layout.addLayout(header_layout)

        self.playground_edit = QPlainTextEdit()
        self.playground_edit.setPlaceholderText("Type triggers here to test…")
        panel_layout.addWidget(self.playground_edit)

        self.playground_header = self.playground_panel
        self.playground_status = QLabel()

        return self.playground_panel

    def toggle_playground(self, *args, show: bool | None = None) -> None:
        if show is None:
            show = not self.playground_panel.isVisible()
        self.playground_panel.setVisible(show)
        if show:
            sizes = self.vertical_splitter.sizes()
            if len(sizes) == 2 and sizes[1] < 50:
                target_h = 140
                top_h = max(200, sizes[0] - target_h)
                self.vertical_splitter.setSizes([top_h, target_h])
            self.playground_edit.setFocus()

    def clear_playground(self) -> None:
        self.playground_edit.clear()
        self.playground_edit.setFocus()
