"""Drag-and-drop widgets for moving matches between configuration files."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QDrag, QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QTableWidget, QTreeWidget


MATCH_INDEX_MIME_TYPE = "application/x-espanso-match-index"


class MatchTableWidget(QTableWidget):
    """A match table that exports the source match index through drag-and-drop."""

    def __init__(self) -> None:
        super().__init__()
        self.setDragEnabled(True)

    def startDrag(self, supported_actions: Qt.DropAction) -> None:
        rows = self.selectionModel().selectedRows()
        if not rows:
            return
        item = self.item(rows[0].row(), 0)
        match_index = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(match_index, int):
            return

        mime_data = QMimeData()
        mime_data.setData(MATCH_INDEX_MIME_TYPE, str(match_index).encode())
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.MoveAction)


class MatchFileTreeWidget(QTreeWidget):
    """A file tree that accepts match drops on configuration files."""

    def __init__(self, move_match: Callable[[int, Path], None]) -> None:
        super().__init__()
        self._move_match = move_match
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(MATCH_INDEX_MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        path = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if event.mimeData().hasFormat(MATCH_INDEX_MIME_TYPE) and isinstance(path, Path):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        path = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        payload = event.mimeData().data(MATCH_INDEX_MIME_TYPE)
        try:
            match_index = int(bytes(payload).decode())
        except (UnicodeDecodeError, ValueError):
            event.ignore()
            return
        if not isinstance(path, Path):
            event.ignore()
            return
        self._move_match(match_index, path)
        event.acceptProposedAction()
