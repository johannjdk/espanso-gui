"""Espanso expansion statistics dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config_service import ConfigService


class StatsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, config_dir: Path | None = None) -> None:
        super().__init__(parent)
        options_dir = config_dir or ConfigService.detect_options_path()
        if options_dir.name == "match":
            candidate = options_dir.parent / "config"
            if candidate.is_dir():
                options_dir = candidate
        self.config_dir = options_dir
        self.version = ConfigService.detect_espanso_version()
        self.supported = ConfigService.is_stats_supported()
        self.enabled = ConfigService.is_stats_enabled(self.config_dir)

        self.setWindowTitle("Espanso statistics")
        self.resize(680, 500)

        layout = QVBoxLayout(self)

        if not self.supported:
            ver_text = self.version if self.version else "not installed"
            warn_label = QLabel(
                f"Statistics tracking requires Espanso 2.4.0 or newer (detected: {ver_text})."
            )
            layout.addWidget(warn_label)
        elif not self.enabled:
            note_row = QHBoxLayout()
            note_label = QLabel(
                "Note: Statistics tracking is disabled in default.yml. Expansions are not recorded."
            )
            note_label.setEnabled(False)
            note_row.addWidget(note_label)
            if parent is not None and hasattr(parent, "open_espanso_configuration"):
                open_cfg_btn = QPushButton("Open configuration…")
                open_cfg_btn.clicked.connect(lambda: (self.accept(), parent.open_espanso_configuration()))
                note_row.addWidget(open_cfg_btn)
            note_row.addStretch()
            layout.addLayout(note_row)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Period:"))
        self.period_combo = QComboBox()
        self.period_combo.addItem("All time", "all")
        self.period_combo.addItem("Today", "today")
        self.period_combo.addItem("Past week", "week")
        self.period_combo.addItem("Past month", "month")
        self.period_combo.addItem("Past year", "year")
        self.period_combo.currentIndexChanged.connect(self.refresh_stats)
        toolbar.addWidget(self.period_combo)

        toolbar.addWidget(QLabel("Filter (LIKE):"))
        self.grep_edit = QLineEdit()
        self.grep_edit.setPlaceholderText("e.g. :%")
        self.grep_edit.setClearButtonEnabled(True)
        self.grep_edit.returnPressed.connect(self.refresh_stats)
        toolbar.addWidget(self.grep_edit, 1)

        toolbar.addWidget(QLabel("Limit:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(5, 500)
        self.limit_spin.setValue(50)
        self.limit_spin.valueChanged.connect(self.refresh_stats)
        toolbar.addWidget(self.limit_spin)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_stats)
        toolbar.addWidget(self.refresh_btn)

        layout.addLayout(toolbar)

        summary_layout = QHBoxLayout()
        self.total_label = QLabel("Total expansions: 0")
        self.unique_label = QLabel("Unique triggers: 0")
        summary_font = self.total_label.font()
        summary_font.setBold(True)
        self.total_label.setFont(summary_font)
        self.unique_label.setFont(summary_font)
        summary_layout.addWidget(self.total_label)
        summary_layout.addWidget(self.unique_label)
        summary_layout.addStretch()
        layout.addLayout(summary_layout)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Trigger", "Expansions", "Share"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        bottom_bar = QHBoxLayout()
        self.clear_btn = QPushButton("Clear database…")
        self.clear_btn.clicked.connect(self.clear_database)
        bottom_bar.addWidget(self.clear_btn)
        bottom_bar.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(close_btn)
        layout.addLayout(bottom_bar)

        if not self.supported:
            self.period_combo.setEnabled(False)
            self.grep_edit.setEnabled(False)
            self.limit_spin.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
        else:
            self.refresh_stats()

    def refresh_stats(self) -> None:
        period = self.period_combo.currentData() or "all"
        grep = self.grep_edit.text().strip() or None
        count = self.limit_spin.value()

        try:
            data = ConfigService.get_stats(period=period, count=count, grep=grep)
        except Exception as error:
            self.total_label.setText("Error loading statistics")
            self.unique_label.setText(str(error))
            self.table.setRowCount(0)
            return

        total = data.get("total", 0)
        unique = data.get("unique", 0)
        self.total_label.setText(f"Total expansions: {total:,}")
        self.unique_label.setText(f"Unique triggers: {unique:,}")

        items = data.get("top", [])
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            trigger = item.get("trigger", "")
            cnt = item.get("count", 0)
            share = (cnt / total * 100) if total > 0 else 0.0

            rank_item = QTableWidgetItem()
            rank_item.setData(Qt.ItemDataRole.DisplayRole, row + 1)
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, rank_item)

            trig_item = QTableWidgetItem(trigger)
            self.table.setItem(row, 1, trig_item)

            count_item = QTableWidgetItem()
            count_item.setData(Qt.ItemDataRole.DisplayRole, cnt)
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 2, count_item)

            share_item = QTableWidgetItem(f"{share:.1f}%")
            share_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, share_item)

        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    def clear_database(self) -> None:
        if QMessageBox.question(
            self,
            "Clear statistics",
            "Are you sure you want to clear all recorded statistics?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        proc = ConfigService.clear_stats()
        if proc.returncode != 0:
            QMessageBox.critical(self, "Clear failed", proc.stderr.strip() or "Failed to clear database")
            return

        self.refresh_stats()
