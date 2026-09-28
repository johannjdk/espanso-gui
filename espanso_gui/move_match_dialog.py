"""Destination picker for moving a match to another configuration file."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget


def choose_match_destination(parent: QWidget, destinations: list[Path]) -> Path | None:
    """Let the user select the configuration file that receives a match."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Move match")
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Move the selected match to:"))

    destination_picker = QComboBox()
    for path in destinations:
        destination_picker.addItem(path.name, path)
    layout.addWidget(destination_picker)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    buttons.addButton("Move", QDialogButtonBox.ButtonRole.AcceptRole)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    destination = destination_picker.currentData()
    return destination if isinstance(destination, Path) else None
