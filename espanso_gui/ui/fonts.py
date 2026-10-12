"""Font helper utilities."""

from __future__ import annotations

from PySide6.QtGui import QFont


def mono_font(size: int = 10) -> QFont:
    font = QFont()
    font.setFamilies([
        "JetBrains Mono",
        "Cascadia Code",
        "Fira Code",
        "DejaVu Sans Mono",
        "Consolas",
        "Menlo",
        "Liberation Mono",
        "monospace",
    ])
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSize(size)
    return font
