"""Espanso configuration profiles dialog."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config_service import ConfigService
from ..ui.stats_dialog import StatsDialog


class NewProfileDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New profile")
        self.resize(360, 200)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. chrome, telegram, vscode")
        form.addRow("Profile name:", self.name_edit)
        layout.addLayout(form)

        type_group = QGroupBox("Profile template")
        type_layout = QVBoxLayout(type_group)
        self.radio_app = QRadioButton("App-specific profile")
        self.radio_disabled = QRadioButton("Disabled in app (enable: false)")
        self.radio_blank = QRadioButton("Blank profile")
        self.radio_app.setChecked(True)
        type_layout.addWidget(self.radio_app)
        type_layout.addWidget(self.radio_disabled)
        type_layout.addWidget(self.radio_blank)
        layout.addWidget(type_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_profile_data(self) -> tuple[str, str] | None:
        raw_name = self.name_edit.text().strip()
        if not raw_name:
            return None
        if not raw_name.endswith(".yml"):
            raw_name += ".yml"
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.yml", raw_name):
            return None

        stem = raw_name[:-4]
        if self.radio_disabled.isChecked():
            content = f'filter_exec: "{stem}"\nenable: false\n'
        elif self.radio_app.isChecked():
            content = f'filter_exec: "{stem}"\n'
        else:
            content = "# Espanso configuration profile\n"

        return raw_name, content


class EspansoConfigDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        options_path = ConfigService.detect_options_path()
        if parent is not None and hasattr(parent, "config_path"):
            candidate = parent.config_path.parent / "config"
            if candidate.is_dir():
                options_path = candidate
        self.config_dir = options_path

        self.current_path: Path | None = None
        self._doc: dict = {}
        self._populating: bool = False
        self._visual_modified: bool = False
        self._last_tab_index: int = 0

        self.setWindowTitle("Espanso configuration")
        self.resize(960, 660)

        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_editor_area())
        splitter.setSizes([240, 720])
        main_layout.addWidget(splitter, 1)

        bottom_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        bottom_buttons.accepted.connect(self.save_current_profile)
        bottom_buttons.rejected.connect(self.reject)
        self.save_button = bottom_buttons.button(QDialogButtonBox.StandardButton.Save)
        main_layout.addWidget(bottom_buttons)

        self._load_profiles()

    def _build_sidebar(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Configuration profiles"))
        self.profile_list = QListWidget()
        self.profile_list.currentTextChanged.connect(self._select_profile)
        layout.addWidget(self.profile_list, 1)

        btn_row = QHBoxLayout()
        self.new_btn = QPushButton("New…")
        self.delete_btn = QPushButton("Delete")
        self.new_btn.clicked.connect(self.new_profile)
        self.delete_btn.clicked.connect(self.delete_profile)
        btn_row.addWidget(self.new_btn)
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

        return panel

    def _build_editor_area(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 0, 0, 0)

        header_layout = QVBoxLayout()
        self.profile_title = QLabel("Select a profile")
        title_font = self.profile_title.font()
        title_font.setBold(True)
        self.profile_title.setFont(title_font)
        header_layout.addWidget(self.profile_title)

        self.profile_desc = QLabel("")
        self.profile_desc.setEnabled(False)
        header_layout.addWidget(self.profile_desc)
        layout.addLayout(header_layout)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.tabs.addTab(self._build_filters_tab(), "Filters")
        self.tabs.addTab(self._build_general_tab(), "General")
        self.tabs.addTab(self._build_search_tab(), "Search")
        self.tabs.addTab(self._build_injection_tab(), "Expansion")
        self.tabs.addTab(self._build_includes_tab(), "Includes")
        self.tabs.addTab(self._build_yaml_tab(), "YAML")

        layout.addWidget(self.tabs, 1)
        return panel

    def _build_filters_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.filter_notice = QLabel(
            "default.yml applies globally to all applications. "
            "Application filters only take effect in app-specific configuration files."
        )
        self.filter_notice.setWordWrap(True)
        self.filter_notice.setEnabled(False)
        layout.addWidget(self.filter_notice)

        self.filter_fields_group = QGroupBox("Application matching")
        form = QFormLayout(self.filter_fields_group)

        self.filter_exec = QLineEdit()
        self.filter_exec.setPlaceholderText("e.g. Telegram, code, chrome.exe")
        self.filter_exec.textChanged.connect(self._mark_visual_modified)
        form.addRow("Executable (regex):", self.filter_exec)

        self.filter_class = QLineEdit()
        self.filter_class.setPlaceholderText("e.g. code-oss, Slack, com.apple.TextEdit")
        self.filter_class.textChanged.connect(self._mark_visual_modified)
        form.addRow("Window class (regex):", self.filter_class)

        self.filter_title = QLineEdit()
        self.filter_title.setPlaceholderText("e.g. Google Chrome, Visual Studio Code")
        self.filter_title.textChanged.connect(self._mark_visual_modified)
        form.addRow("Window title (regex):", self.filter_title)

        self.filter_os = QComboBox()
        self.filter_os.addItems(["Any", "linux", "macos", "windows"])
        self.filter_os.currentIndexChanged.connect(self._mark_visual_modified)
        form.addRow("Operating system:", self.filter_os)

        layout.addWidget(self.filter_fields_group)

        self.filter_tip = QLabel("Note: Type #detect# in any application to inspect its executable, class and title.")
        self.filter_tip.setEnabled(False)
        layout.addWidget(self.filter_tip)

        layout.addStretch()
        return widget

    def _build_general_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        layout = QVBoxLayout(widget)

        status_group = QGroupBox("Profile status")
        status_form = QFormLayout(status_group)

        self.enable_cb = QCheckBox("Enable Espanso in this profile")
        self.enable_cb.setChecked(True)
        self.enable_cb.stateChanged.connect(self._mark_visual_modified)
        status_form.addRow("Status:", self.enable_cb)

        self.toggle_key = QComboBox()
        self.toggle_key.addItems([
            "OFF", "ALT", "CTRL", "SHIFT", "META",
            "LEFT_ALT", "RIGHT_ALT", "LEFT_CTRL", "RIGHT_CTRL",
            "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_META", "RIGHT_META",
        ])
        self.toggle_key.currentIndexChanged.connect(self._mark_visual_modified)
        status_form.addRow("Toggle key (double tap):", self.toggle_key)

        layout.addWidget(status_group)

        self.global_group = QGroupBox("Global options (default.yml)")
        global_layout = QVBoxLayout(self.global_group)

        self.show_icon_cb = QCheckBox("Show tray / menu bar status icon")
        self.show_notifications_cb = QCheckBox("Show desktop notifications")
        self.auto_restart_cb = QCheckBox("Auto-restart daemon on configuration changes")
        self.undo_backspace_cb = QCheckBox("Revert expansion on immediate Backspace")

        for cb in (self.show_icon_cb, self.show_notifications_cb, self.auto_restart_cb, self.undo_backspace_cb):
            cb.stateChanged.connect(self._mark_visual_modified)
            global_layout.addWidget(cb)

        stats_row = QHBoxLayout()
        self.stats_cb = QCheckBox("Enable usage statistics (stats)")
        self.stats_cb.stateChanged.connect(self._mark_visual_modified)
        self.view_stats_btn = QPushButton("View statistics…")
        self.view_stats_btn.clicked.connect(self._open_stats_dialog)
        self.stats_cb.toggled.connect(self.view_stats_btn.setEnabled)
        stats_row.addWidget(self.stats_cb)
        stats_row.addWidget(self.view_stats_btn)
        stats_row.addStretch()
        global_layout.addLayout(stats_row)

        bs_form = QFormLayout()
        self.backspace_limit_sb = QSpinBox()
        self.backspace_limit_sb.setRange(1, 100)
        self.backspace_limit_sb.setValue(5)
        self.backspace_limit_sb.valueChanged.connect(self._mark_visual_modified)
        bs_form.addRow("Backspace undo limit:", self.backspace_limit_sb)
        global_layout.addLayout(bs_form)

        layout.addWidget(self.global_group)

        self.kb_group = QGroupBox("Keyboard layout (Wayland / Linux override)")
        kb_form = QFormLayout(self.kb_group)

        self.kl_layout = QLineEdit()
        self.kl_layout.setPlaceholderText("e.g. de, us")
        self.kl_layout.textChanged.connect(self._mark_visual_modified)
        kb_form.addRow("Layout:", self.kl_layout)

        self.kl_variant = QLineEdit()
        self.kl_variant.setPlaceholderText("e.g. nodeadkeys")
        self.kl_variant.textChanged.connect(self._mark_visual_modified)
        kb_form.addRow("Variant:", self.kl_variant)

        self.kl_model = QLineEdit()
        self.kl_model.setPlaceholderText("e.g. pc105")
        self.kl_model.textChanged.connect(self._mark_visual_modified)
        kb_form.addRow("Model:", self.kl_model)

        self.kl_options = QLineEdit()
        self.kl_options.setPlaceholderText("e.g. ctrl:nocaps")
        self.kl_options.textChanged.connect(self._mark_visual_modified)
        kb_form.addRow("Options:", self.kl_options)

        self.kl_rules = QLineEdit()
        self.kl_rules.setPlaceholderText("e.g. evdev")
        self.kl_rules.textChanged.connect(self._mark_visual_modified)
        kb_form.addRow("Rules:", self.kl_rules)

        layout.addWidget(self.kb_group)
        layout.addStretch()

        scroll.setWidget(widget)
        return scroll

    def _build_search_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Search bar")
        form = QFormLayout(group)

        self.search_shortcut = QLineEdit()
        self.search_shortcut.setPlaceholderText("ALT+Space (or off)")
        self.search_shortcut.textChanged.connect(self._mark_visual_modified)
        form.addRow("Search shortcut:", self.search_shortcut)

        self.search_trigger = QLineEdit()
        self.search_trigger.setPlaceholderText("e.g. .search (or off)")
        self.search_trigger.textChanged.connect(self._mark_visual_modified)
        form.addRow("Search trigger:", self.search_trigger)

        self.post_search_delay_sb = QSpinBox()
        self.post_search_delay_sb.setRange(0, 5000)
        self.post_search_delay_sb.setSingleStep(50)
        self.post_search_delay_sb.setSuffix(" ms")
        self.post_search_delay_sb.setValue(200)
        self.post_search_delay_sb.valueChanged.connect(self._mark_visual_modified)
        form.addRow("Post-search delay:", self.post_search_delay_sb)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _build_injection_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        layout = QVBoxLayout(widget)

        inj_group = QGroupBox("Injection and clipboard")
        form = QFormLayout(inj_group)

        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["auto", "clipboard", "inject"])
        self.backend_combo.currentIndexChanged.connect(self._mark_visual_modified)
        form.addRow("Backend:", self.backend_combo)

        self.clipboard_threshold_sb = QSpinBox()
        self.clipboard_threshold_sb.setRange(10, 50000)
        self.clipboard_threshold_sb.setSingleStep(25)
        self.clipboard_threshold_sb.setSuffix(" chars")
        self.clipboard_threshold_sb.setValue(100)
        self.clipboard_threshold_sb.valueChanged.connect(self._mark_visual_modified)
        form.addRow("Clipboard threshold:", self.clipboard_threshold_sb)

        self.preserve_clipboard_cb = QCheckBox("Preserve clipboard content after expansion")
        self.preserve_clipboard_cb.setChecked(True)
        self.preserve_clipboard_cb.stateChanged.connect(self._mark_visual_modified)
        form.addRow("Clipboard restore:", self.preserve_clipboard_cb)

        self.paste_shortcut = QLineEdit()
        self.paste_shortcut.setPlaceholderText("e.g. CTRL+V or CTRL+SHIFT+V")
        self.paste_shortcut.textChanged.connect(self._mark_visual_modified)
        form.addRow("Custom paste shortcut:", self.paste_shortcut)

        layout.addWidget(inj_group)

        delays_group = QGroupBox("Delays")
        delays_form = QFormLayout(delays_group)

        self.pre_paste_delay_sb = QSpinBox()
        self.pre_paste_delay_sb.setRange(0, 5000)
        self.pre_paste_delay_sb.setSuffix(" ms")
        self.pre_paste_delay_sb.setValue(300)
        self.pre_paste_delay_sb.valueChanged.connect(self._mark_visual_modified)
        delays_form.addRow("Pre-paste delay:", self.pre_paste_delay_sb)

        self.restore_clipboard_delay_sb = QSpinBox()
        self.restore_clipboard_delay_sb.setRange(0, 5000)
        self.restore_clipboard_delay_sb.setSuffix(" ms")
        self.restore_clipboard_delay_sb.setValue(300)
        self.restore_clipboard_delay_sb.valueChanged.connect(self._mark_visual_modified)
        delays_form.addRow("Restore clipboard delay:", self.restore_clipboard_delay_sb)

        self.inject_delay_sb = QSpinBox()
        self.inject_delay_sb.setRange(0, 5000)
        self.inject_delay_sb.setSuffix(" ms")
        self.inject_delay_sb.setValue(0)
        self.inject_delay_sb.valueChanged.connect(self._mark_visual_modified)
        delays_form.addRow("Text injection delay:", self.inject_delay_sb)

        self.key_delay_sb = QSpinBox()
        self.key_delay_sb.setRange(0, 5000)
        self.key_delay_sb.setSuffix(" ms")
        self.key_delay_sb.setValue(0)
        self.key_delay_sb.valueChanged.connect(self._mark_visual_modified)
        delays_form.addRow("Key injection delay:", self.key_delay_sb)

        self.paste_shortcut_event_delay_sb = QSpinBox()
        self.paste_shortcut_event_delay_sb.setRange(0, 5000)
        self.paste_shortcut_event_delay_sb.setSuffix(" ms")
        self.paste_shortcut_event_delay_sb.setValue(10)
        self.paste_shortcut_event_delay_sb.valueChanged.connect(self._mark_visual_modified)
        delays_form.addRow("Paste shortcut event delay:", self.paste_shortcut_event_delay_sb)

        layout.addWidget(delays_group)

        forms_group = QGroupBox("Forms")
        forms_layout = QFormLayout(forms_group)

        self.max_form_width_sb = QSpinBox()
        self.max_form_width_sb.setRange(200, 3000)
        self.max_form_width_sb.setSuffix(" px")
        self.max_form_width_sb.setValue(700)
        self.max_form_width_sb.valueChanged.connect(self._mark_visual_modified)
        forms_layout.addRow("Max form width:", self.max_form_width_sb)

        self.max_form_height_sb = QSpinBox()
        self.max_form_height_sb.setRange(200, 3000)
        self.max_form_height_sb.setSuffix(" px")
        self.max_form_height_sb.setValue(500)
        self.max_form_height_sb.valueChanged.connect(self._mark_visual_modified)
        forms_layout.addRow("Max form height:", self.max_form_height_sb)

        self.post_form_delay_sb = QSpinBox()
        self.post_form_delay_sb.setRange(0, 5000)
        self.post_form_delay_sb.setSuffix(" ms")
        self.post_form_delay_sb.setValue(200)
        self.post_form_delay_sb.valueChanged.connect(self._mark_visual_modified)
        forms_layout.addRow("Post-form delay:", self.post_form_delay_sb)

        layout.addWidget(forms_group)
        layout.addStretch()

        scroll.setWidget(widget)
        return scroll

    def _build_includes_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        inc_group = QGroupBox("Extra includes (extra_includes)")
        inc_layout = QVBoxLayout(inc_group)
        self.extra_includes_list = QListWidget()
        inc_layout.addWidget(self.extra_includes_list)

        inc_btn_row = QHBoxLayout()
        add_inc_file_btn = QPushButton("Add match file…")
        add_inc_custom_btn = QPushButton("Add path…")
        rem_inc_btn = QPushButton("Remove")
        add_inc_file_btn.clicked.connect(self._add_include_file)
        add_inc_custom_btn.clicked.connect(self._add_include_custom)
        rem_inc_btn.clicked.connect(lambda: self._remove_list_item(self.extra_includes_list))
        inc_btn_row.addWidget(add_inc_file_btn)
        inc_btn_row.addWidget(add_inc_custom_btn)
        inc_btn_row.addWidget(rem_inc_btn)
        inc_btn_row.addStretch()
        inc_layout.addLayout(inc_btn_row)
        layout.addWidget(inc_group)

        exc_group = QGroupBox("Extra excludes (extra_excludes)")
        exc_layout = QVBoxLayout(exc_group)
        self.extra_excludes_list = QListWidget()
        exc_layout.addWidget(self.extra_excludes_list)

        exc_btn_row = QHBoxLayout()
        add_exc_btn = QPushButton("Add rule…")
        rem_exc_btn = QPushButton("Remove")
        add_exc_btn.clicked.connect(self._add_exclude_rule)
        rem_exc_btn.clicked.connect(lambda: self._remove_list_item(self.extra_excludes_list))
        exc_btn_row.addWidget(add_exc_btn)
        exc_btn_row.addWidget(rem_exc_btn)
        exc_btn_row.addStretch()
        exc_layout.addLayout(exc_btn_row)
        layout.addWidget(exc_group)

        std_group = QGroupBox("Standard includes")
        std_form = QFormLayout(std_group)
        self.use_standard_includes_combo = QComboBox()
        self.use_standard_includes_combo.addItems([
            "Default (auto)",
            "True (include standard matches)",
            "False (exclude standard matches)",
        ])
        self.use_standard_includes_combo.currentIndexChanged.connect(self._mark_visual_modified)
        std_form.addRow("use_standard_includes:", self.use_standard_includes_combo)
        layout.addWidget(std_group)

        return widget

    def _build_yaml_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Raw YAML configuration (Expert mode)"))

        self.editor = QPlainTextEdit()
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(10)
        self.editor.setFont(font)
        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(" ") * 2)
        layout.addWidget(self.editor, 1)

        return widget

    def _load_profiles(self, selected_path: Path | None = None) -> None:
        paths: list[Path] = []
        if self.config_dir.is_dir():
            paths = sorted(self.config_dir.glob("*.yml"), key=lambda p: (p.name != "default.yml", p.name.lower()))

        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        for path in paths:
            self.profile_list.addItem(path.name)
        self.profile_list.blockSignals(False)

        target = selected_path or self.current_path
        if target is not None and target in paths:
            self.profile_list.setCurrentRow(paths.index(target))
        elif paths:
            self.profile_list.setCurrentRow(0)
        else:
            self.current_path = None
            self.profile_title.setText("No profile selected")
            self.profile_desc.setText("")
            self.editor.clear()
            self.editor.setEnabled(False)
            self.save_button.setEnabled(False)

    def _select_profile(self, name: str) -> None:
        if not name:
            return
        path = self.config_dir / name
        if path == self.current_path:
            return
        if not self._confirm_profile_change():
            self.profile_list.blockSignals(True)
            if self.current_path is not None:
                matches = self.profile_list.findItems(self.current_path.name, Qt.MatchFlag.MatchExactly)
                if matches:
                    self.profile_list.setCurrentItem(matches[0])
            self.profile_list.blockSignals(False)
            return

        try:
            source = path.read_text(encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(self, "Open failed", str(error))
            return

        self.current_path = path
        is_default = path.name == "default.yml"

        self.profile_title.setText(path.name)
        if is_default:
            self.profile_desc.setText("Base configuration (applies to all applications)")
            self.filter_notice.setText(
                "default.yml applies globally to all applications. "
                "Application filters only take effect in app-specific configuration files."
            )
            self.filter_fields_group.setEnabled(False)
            self.global_group.setEnabled(True)
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip("default.yml is required by Espanso and cannot be deleted")
        else:
            self.profile_desc.setText("App-specific profile (active when matching application filters)")
            self.filter_notice.setText("Filter rules determine when this profile is active (values match by regex).")
            self.filter_fields_group.setEnabled(True)
            self.global_group.setEnabled(False)
            self.delete_btn.setEnabled(True)
            self.delete_btn.setToolTip("Delete this configuration profile")

        try:
            parsed = yaml.safe_load(source) or {}
            self._doc = dict(parsed) if isinstance(parsed, dict) else {}
        except Exception:
            self._doc = {}

        self._populate_visual_form(self._doc)
        self.editor.setEnabled(True)
        self.editor.setPlainText(source)
        self.editor.document().setModified(False)
        self._visual_modified = False
        self.save_button.setEnabled(True)

    def _populate_visual_form(self, doc: dict) -> None:
        self._populating = True

        self.filter_exec.setText(str(doc.get("filter_exec", "") or ""))
        self.filter_class.setText(str(doc.get("filter_class", "") or ""))
        self.filter_title.setText(str(doc.get("filter_title", "") or ""))
        target_os = str(doc.get("filter_os", "") or "").lower()
        os_idx = {"linux": 1, "macos": 2, "windows": 3}.get(target_os, 0)
        self.filter_os.setCurrentIndex(os_idx)

        self.enable_cb.setChecked(bool(doc.get("enable", True)))

        raw_key = doc.get("toggle_key", "OFF")
        if raw_key is False or raw_key is None:
            raw_key = "OFF"
        key_str = str(raw_key).upper()
        idx = self.toggle_key.findText(key_str)
        self.toggle_key.setCurrentIndex(idx if idx >= 0 else 0)

        self.show_icon_cb.setChecked(bool(doc.get("show_icon", True)))
        self.show_notifications_cb.setChecked(bool(doc.get("show_notifications", True)))
        self.auto_restart_cb.setChecked(bool(doc.get("auto_restart", True)))
        self.undo_backspace_cb.setChecked(bool(doc.get("undo_backspace", True)))
        self.backspace_limit_sb.setValue(int(doc.get("backspace_limit", 5)))

        stats_val = doc.get("stats")
        if isinstance(stats_val, dict):
            self.stats_cb.setChecked(bool(stats_val.get("enabled", False)))
        elif isinstance(stats_val, bool):
            self.stats_cb.setChecked(stats_val)
        else:
            self.stats_cb.setChecked(False)
        self.view_stats_btn.setEnabled(self.stats_cb.isChecked())

        kl = doc.get("keyboard_layout")
        if isinstance(kl, dict):
            self.kl_layout.setText(str(kl.get("layout", "") or ""))
            self.kl_variant.setText(str(kl.get("variant", "") or ""))
            self.kl_model.setText(str(kl.get("model", "") or ""))
            self.kl_options.setText(str(kl.get("options", "") or ""))
            self.kl_rules.setText(str(kl.get("rules", "") or ""))
        else:
            self.kl_layout.clear()
            self.kl_variant.clear()
            self.kl_model.clear()
            self.kl_options.clear()
            self.kl_rules.clear()

        self.search_shortcut.setText(str(doc.get("search_shortcut", "") or ""))
        self.search_trigger.setText(str(doc.get("search_trigger", "") or ""))
        self.post_search_delay_sb.setValue(int(doc.get("post_search_delay", 200)))

        backend_val = str(doc.get("backend", "auto")).lower()
        b_idx = self.backend_combo.findText(backend_val)
        self.backend_combo.setCurrentIndex(b_idx if b_idx >= 0 else 0)
        self.clipboard_threshold_sb.setValue(int(doc.get("clipboard_threshold", 100)))
        self.preserve_clipboard_cb.setChecked(bool(doc.get("preserve_clipboard", True)))
        self.paste_shortcut.setText(str(doc.get("paste_shortcut", "") or ""))

        self.pre_paste_delay_sb.setValue(int(doc.get("pre_paste_delay", 300)))
        self.restore_clipboard_delay_sb.setValue(int(doc.get("restore_clipboard_delay", 300)))
        self.inject_delay_sb.setValue(int(doc.get("inject_delay", 0)))
        self.key_delay_sb.setValue(int(doc.get("key_delay", 0)))
        self.paste_shortcut_event_delay_sb.setValue(int(doc.get("paste_shortcut_event_delay", 10)))
        self.post_form_delay_sb.setValue(int(doc.get("post_form_delay", 200)))
        self.max_form_width_sb.setValue(int(doc.get("max_form_width", 700)))
        self.max_form_height_sb.setValue(int(doc.get("max_form_height", 500)))

        self.extra_includes_list.clear()
        raw_includes = doc.get("extra_includes", [])
        if isinstance(raw_includes, list):
            for inc in raw_includes:
                self.extra_includes_list.addItem(str(inc))
        elif isinstance(raw_includes, str):
            self.extra_includes_list.addItem(raw_includes)

        self.extra_excludes_list.clear()
        raw_excludes = doc.get("extra_excludes", [])
        if isinstance(raw_excludes, list):
            for exc in raw_excludes:
                self.extra_excludes_list.addItem(str(exc))
        elif isinstance(raw_excludes, str):
            self.extra_excludes_list.addItem(raw_excludes)

        std_inc = doc.get("use_standard_includes")
        if std_inc is True:
            self.use_standard_includes_combo.setCurrentIndex(1)
        elif std_inc is False:
            self.use_standard_includes_combo.setCurrentIndex(2)
        else:
            self.use_standard_includes_combo.setCurrentIndex(0)

        self._populating = False
        self._visual_modified = False

    def _collect_visual_form_into_doc(self) -> None:
        is_default = self.current_path is not None and self.current_path.name == "default.yml"

        if not is_default:
            exec_val = self.filter_exec.text().strip()
            if exec_val:
                self._doc["filter_exec"] = exec_val
            elif "filter_exec" in self._doc:
                del self._doc["filter_exec"]

            class_val = self.filter_class.text().strip()
            if class_val:
                self._doc["filter_class"] = class_val
            elif "filter_class" in self._doc:
                del self._doc["filter_class"]

            title_val = self.filter_title.text().strip()
            if title_val:
                self._doc["filter_title"] = title_val
            elif "filter_title" in self._doc:
                del self._doc["filter_title"]

            os_idx = self.filter_os.currentIndex()
            if os_idx > 0:
                self._doc["filter_os"] = self.filter_os.currentText()
            elif "filter_os" in self._doc:
                del self._doc["filter_os"]

        if not self.enable_cb.isChecked():
            self._doc["enable"] = False
        elif "enable" in self._doc:
            self._doc["enable"] = True

        tkey = self.toggle_key.currentText()
        if tkey == "OFF":
            if "toggle_key" in self._doc:
                self._doc["toggle_key"] = "OFF"
        else:
            self._doc["toggle_key"] = tkey

        if is_default:
            if not self.show_icon_cb.isChecked() or "show_icon" in self._doc:
                self._doc["show_icon"] = self.show_icon_cb.isChecked()
            if not self.show_notifications_cb.isChecked() or "show_notifications" in self._doc:
                self._doc["show_notifications"] = self.show_notifications_cb.isChecked()
            if not self.auto_restart_cb.isChecked() or "auto_restart" in self._doc:
                self._doc["auto_restart"] = self.auto_restart_cb.isChecked()
            if not self.undo_backspace_cb.isChecked() or "undo_backspace" in self._doc:
                self._doc["undo_backspace"] = self.undo_backspace_cb.isChecked()
            if self.backspace_limit_sb.value() != 5 or "backspace_limit" in self._doc:
                self._doc["backspace_limit"] = self.backspace_limit_sb.value()
            if self.stats_cb.isChecked() or "stats" in self._doc:
                if isinstance(self._doc.get("stats"), dict):
                    self._doc["stats"]["enabled"] = self.stats_cb.isChecked()
                else:
                    self._doc["stats"] = {"enabled": self.stats_cb.isChecked()}
        elif "undo_backspace" in self._doc or not self.undo_backspace_cb.isChecked():
            self._doc["undo_backspace"] = self.undo_backspace_cb.isChecked()

        kl_data = {}
        for field, widget in (
            ("layout", self.kl_layout),
            ("variant", self.kl_variant),
            ("model", self.kl_model),
            ("options", self.kl_options),
            ("rules", self.kl_rules),
        ):
            text = widget.text().strip()
            if text:
                kl_data[field] = text

        if kl_data:
            if isinstance(self._doc.get("keyboard_layout"), dict):
                self._doc["keyboard_layout"].update(kl_data)
                for k in list(self._doc["keyboard_layout"].keys()):
                    if k in ("layout", "variant", "model", "options", "rules") and k not in kl_data:
                        del self._doc["keyboard_layout"][k]
            else:
                self._doc["keyboard_layout"] = kl_data
        elif "keyboard_layout" in self._doc:
            del self._doc["keyboard_layout"]

        s_cut = self.search_shortcut.text().strip()
        if s_cut:
            self._doc["search_shortcut"] = s_cut
        elif "search_shortcut" in self._doc:
            del self._doc["search_shortcut"]

        s_trig = self.search_trigger.text().strip()
        if s_trig:
            self._doc["search_trigger"] = s_trig
        elif "search_trigger" in self._doc:
            del self._doc["search_trigger"]

        if self.post_search_delay_sb.value() != 200 or "post_search_delay" in self._doc:
            self._doc["post_search_delay"] = self.post_search_delay_sb.value()

        b_val = self.backend_combo.currentText().lower()
        if b_val != "auto" or "backend" in self._doc:
            self._doc["backend"] = b_val

        if self.clipboard_threshold_sb.value() != 100 or "clipboard_threshold" in self._doc:
            self._doc["clipboard_threshold"] = self.clipboard_threshold_sb.value()

        if not self.preserve_clipboard_cb.isChecked() or "preserve_clipboard" in self._doc:
            self._doc["preserve_clipboard"] = self.preserve_clipboard_cb.isChecked()

        p_sc = self.paste_shortcut.text().strip()
        if p_sc:
            self._doc["paste_shortcut"] = p_sc
        elif "paste_shortcut" in self._doc:
            del self._doc["paste_shortcut"]

        delays = [
            ("pre_paste_delay", self.pre_paste_delay_sb.value(), 300),
            ("restore_clipboard_delay", self.restore_clipboard_delay_sb.value(), 300),
            ("inject_delay", self.inject_delay_sb.value(), 0),
            ("key_delay", self.key_delay_sb.value(), 0),
            ("paste_shortcut_event_delay", self.paste_shortcut_event_delay_sb.value(), 10),
            ("post_form_delay", self.post_form_delay_sb.value(), 200),
            ("max_form_width", self.max_form_width_sb.value(), 700),
            ("max_form_height", self.max_form_height_sb.value(), 500),
        ]
        for key, val, default_val in delays:
            if val != default_val or key in self._doc:
                self._doc[key] = val

        inc_items = [self.extra_includes_list.item(i).text() for i in range(self.extra_includes_list.count())]
        if inc_items:
            self._doc["extra_includes"] = inc_items
        elif "extra_includes" in self._doc:
            del self._doc["extra_includes"]

        exc_items = [self.extra_excludes_list.item(i).text() for i in range(self.extra_excludes_list.count())]
        if exc_items:
            self._doc["extra_excludes"] = exc_items
        elif "extra_excludes" in self._doc:
            del self._doc["extra_excludes"]

        std_idx = self.use_standard_includes_combo.currentIndex()
        if std_idx == 1:
            self._doc["use_standard_includes"] = True
        elif std_idx == 2:
            self._doc["use_standard_includes"] = False
        elif "use_standard_includes" in self._doc:
            del self._doc["use_standard_includes"]

    def _mark_visual_modified(self) -> None:
        if self._populating:
            return
        self._visual_modified = True
        self.save_button.setEnabled(True)

    def _on_tab_changed(self, new_index: int) -> None:
        if self._populating:
            return

        # Leaving YAML tab -> update visual controls from YAML
        if self._last_tab_index == 5 and new_index != 5:
            yaml_text = self.editor.toPlainText()
            try:
                parsed = yaml.safe_load(yaml_text) or {}
                if not isinstance(parsed, dict):
                    raise ValueError("The YAML root must be a mapping.")
                self._doc = parsed
                self._populate_visual_form(self._doc)
            except Exception as error:
                QMessageBox.warning(
                    self,
                    "Invalid YAML",
                    f"Could not parse YAML:\n{error}\n\nPlease fix the YAML before returning to visual mode.",
                )
                self.tabs.blockSignals(True)
                self.tabs.setCurrentIndex(5)
                self.tabs.blockSignals(False)
                return

        # Entering YAML tab -> update YAML from visual controls
        elif new_index == 5 and self._last_tab_index != 5:
            if self._visual_modified:
                self._collect_visual_form_into_doc()
                new_yaml = yaml.dump(self._doc, sort_keys=False, default_flow_style=False)
                self.editor.setPlainText(new_yaml)
                self._visual_modified = False
                self.editor.document().setModified(True)

        self._last_tab_index = new_index

    def _add_include_file(self) -> None:
        match_dir = self.config_dir.parent / "match"
        initial_dir = str(match_dir) if match_dir.is_dir() else str(self.config_dir)
        path, _ = QFileDialog.getOpenFileName(self, "Select match file", initial_dir, "YAML (*.yml *.yaml)")
        if not path:
            return
        try:
            rel = os.path.relpath(path, self.config_dir)
        except ValueError:
            rel = path
        self.extra_includes_list.addItem(rel)
        self._mark_visual_modified()

    def _add_include_custom(self) -> None:
        val, ok = QInputDialog.getText(self, "Add include path", "Path to match file (relative to config/):")
        if ok and val.strip():
            self.extra_includes_list.addItem(val.strip())
            self._mark_visual_modified()

    def _add_exclude_rule(self) -> None:
        val, ok = QInputDialog.getText(
            self,
            "Add exclude rule",
            "Path pattern or package to exclude (e.g. ../match/packages/all-emojis/*):",
        )
        if ok and val.strip():
            self.extra_excludes_list.addItem(val.strip())
            self._mark_visual_modified()

    def _remove_list_item(self, list_widget: QListWidget) -> None:
        row = list_widget.currentRow()
        if row >= 0:
            list_widget.takeItem(row)
            self._mark_visual_modified()

    def _confirm_profile_change(self) -> bool:
        if self.current_path is None:
            return True
        is_dirty = self._visual_modified or self.editor.document().isModified()
        if not is_dirty:
            return True

        answer = QMessageBox.warning(
            self,
            "Unsaved configuration",
            f"Save changes to {self.current_path.name}?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return answer != QMessageBox.StandardButton.Save or self.save_current_profile()

    def new_profile(self) -> None:
        dlg = NewProfileDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_profile_data()
        if not data:
            QMessageBox.warning(self, "Invalid name", "Use a valid name ending with .yml (e.g. chrome.yml).")
            return

        name, content = data
        path = self.config_dir / name
        if path.exists():
            QMessageBox.warning(self, "Already exists", f"{name} already exists.")
            return

        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            ConfigService.save_config_yaml(path, content)
        except OSError as error:
            QMessageBox.critical(self, "Create failed", str(error))
            return

        self._load_profiles(path)

    def delete_profile(self) -> None:
        if self.current_path is None or self.current_path.name == "default.yml":
            return
        if not self._confirm_profile_change():
            return

        path = self.current_path
        if (
            QMessageBox.question(
                self,
                "Delete profile",
                f'Really delete configuration profile "{path.name}"?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            path.unlink()
        except OSError as error:
            QMessageBox.critical(self, "Delete failed", str(error))
            return

        self.current_path = None
        self._load_profiles()

    def save_current_profile(self) -> bool:
        if self.current_path is None:
            return False

        if self.tabs.currentIndex() == 5 or (self.editor.document().isModified() and not self._visual_modified):
            yaml_text = self.editor.toPlainText()
            try:
                ConfigService.validate_config_yaml(yaml_text)
            except Exception as error:
                QMessageBox.critical(self, "Invalid configuration", str(error))
                return False
        else:
            self._collect_visual_form_into_doc()
            yaml_text = yaml.dump(self._doc, sort_keys=False, default_flow_style=False)
            self.editor.setPlainText(yaml_text)

        try:
            ConfigService.save_config_yaml(self.current_path, yaml_text)
        except (OSError, ValueError, yaml.YAMLError) as error:
            QMessageBox.critical(self, "Save failed", str(error))
            return False

        self._visual_modified = False
        self.editor.document().setModified(False)
        return True

    def _open_stats_dialog(self) -> None:
        dlg = StatsDialog(self, self.config_dir)
        dlg.exec()

    def reject(self) -> None:
        if self._confirm_profile_change():
            super().reject()
