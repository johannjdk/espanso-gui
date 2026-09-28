"""PySide6 (Qt 6) desktop editor for Espanso YAML match files."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QListWidget,
    QMessageBox, QPushButton, QRadioButton, QScrollArea, QSplitter,
    QPlainTextEdit, QStackedWidget, QStyleFactory, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .about import APP_ID, APP_NAME, show_about_dialog
from .config_service import ConfigService
from .match_drag_drop import MatchFileTreeWidget, MatchTableWidget
from .models import EspansoFormField, EspansoMatch, EspansoVariable
from .move_match_dialog import choose_match_destination


def application_icon() -> QIcon:
    """Return the packaged application icon when one is available."""
    resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    candidates = [
        resource_root / "assets" / "espanso-gui-qt.png",
        Path(f"/usr/share/icons/hicolor/256x256/apps/{APP_ID}.png"),
        Path(f"/usr/share/pixmaps/{APP_ID}.png"),
        # Compatibility with packages built before the standard-size path.
        Path(f"/usr/share/icons/hicolor/160x160/apps/{APP_ID}.png"),
    ]
    for icon_path in candidates:
        if icon_path.is_file():
            return QIcon(str(icon_path))
    return QIcon()


def setup_qt_environment() -> None:
    """Register system Qt6 plugin directories and desktop platform integration."""
    if not sys.platform.startswith("linux"):
        return

    # On Linux, register system Qt6 plugin directories (e.g. /usr/lib/qt6/plugins)
    # so that pip wheels can load system styles (like Breeze) and platform themes.
    qt6_plugin_dirs = [
        "/usr/lib/qt6/plugins",
        "/usr/lib64/qt6/plugins",
        "/usr/lib/x86_64-linux-gnu/qt6/plugins",
        "/usr/lib/aarch64-linux-gnu/qt6/plugins",
        "/usr/local/lib/qt6/plugins",
    ]
    valid_dirs = [d for d in qt6_plugin_dirs if os.path.isdir(d)]
    for d in valid_dirs:
        QCoreApplication.addLibraryPath(d)

    if valid_dirs:
        existing = os.environ.get("QT_PLUGIN_PATH", "")
        existing_list = [p for p in existing.split(os.pathsep) if p]
        new_dirs = [d for d in valid_dirs if d not in existing_list]
        if new_dirs:
            os.environ["QT_PLUGIN_PATH"] = os.pathsep.join(new_dirs + existing_list)

    # In KDE Plasma sessions, ensure QT_QPA_PLATFORMTHEME is set to 'kde'
    # so that Qt integrates with KDE fonts, colors, and Breeze widgets.
    is_kde = os.environ.get("KDE_FULL_SESSION") == "true" or "KDE" in os.environ.get(
        "XDG_CURRENT_DESKTOP", ""
    )
    if is_kde and "QT_QPA_PLATFORMTHEME" not in os.environ:
        os.environ["QT_QPA_PLATFORMTHEME"] = "kde"


def _detect_desktop_style() -> str:
    """Detect the user's preferred desktop style (e.g. Breeze on KDE Plasma)."""
    # 1. Check explicit QT_STYLE_OVERRIDE environment variable
    override = os.environ.get("QT_STYLE_OVERRIDE", "").strip()
    if override:
        return override

    # 2. Check KDE Plasma settings if running under KDE
    is_kde = os.environ.get("KDE_FULL_SESSION") == "true" or "KDE" in os.environ.get(
        "XDG_CURRENT_DESKTOP", ""
    )
    if is_kde:
        for cmd in ("kreadconfig6", "kreadconfig5"):
            if shutil.which(cmd):
                try:
                    res = subprocess.run(
                        [cmd, "--group", "KDE", "--key", "widgetStyle"],
                        capture_output=True,
                        text=True,
                        timeout=1,
                        check=False,
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        return res.stdout.strip()
                except Exception:
                    pass

        # Fallback to checking ~/.config/kdeglobals directly
        config_file = Path.home() / ".config" / "kdeglobals"
        if config_file.is_file():
            try:
                in_kde_group = False
                for line in config_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line.startswith("[") and line.endswith("]"):
                        in_kde_group = line.lower() == "[kde]"
                    elif in_kde_group and line.lower().startswith("widgetstyle="):
                        val = line.split("=", 1)[1].strip()
                        if val:
                            return val
            except Exception:
                pass

        # Default on KDE Plasma is Breeze
        return "Breeze"

    return ""


class EspansoConfigDialog(QDialog):
    """Edit Espanso's default and application-specific configuration profiles."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config_dir = ConfigService.detect_options_path()
        self.current_path: Path | None = None

        self.setWindowTitle("Espanso configuration")
        self.resize(980, 680)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Edit Espanso configuration profiles. <b>default.yml</b> applies everywhere; "
            "other profiles become active when their filter rules match an application."
        ))

        content = QSplitter(Qt.Orientation.Horizontal)
        file_panel = QWidget()
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.addWidget(QLabel("Configuration profiles"))
        self.profile_list = QListWidget()
        self.profile_list.currentTextChanged.connect(self._select_profile)
        file_layout.addWidget(self.profile_list, 1)

        profile_buttons = QHBoxLayout()
        new_profile = QPushButton("New…")
        delete_profile = QPushButton("Delete")
        new_profile.clicked.connect(self.new_profile)
        delete_profile.clicked.connect(self.delete_profile)
        profile_buttons.addWidget(new_profile)
        profile_buttons.addWidget(delete_profile)
        file_layout.addLayout(profile_buttons)
        content.addWidget(file_panel)

        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        self.profile_label = QLabel("No profile selected")
        editor_layout.addWidget(self.profile_label)
        editor_layout.addWidget(QLabel(
            "Use filter_exec, filter_class, filter_title, or filter_os for app profiles. "
            "Includes and excludes accept the standard and extra_ variants. "
            "App-specific profiles are not supported by Espanso on Wayland."
        ))
        self.editor = QPlainTextEdit()
        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(" ") * 2)
        editor_layout.addWidget(self.editor, 1)
        content.addWidget(editor_panel)
        content.setSizes([260, 720])
        layout.addWidget(content, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        buttons.accepted.connect(self.save_current_profile)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self._load_profiles()

    def _load_profiles(self, selected_path: Path | None = None) -> None:
        paths: list[Path] = []
        if self.config_dir.is_dir():
            paths = sorted(self.config_dir.glob("*.yml"), key=lambda path: path.name.lower())
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
            self.profile_label.setText("No profile selected")
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
                matches = self.profile_list.findItems(
                    self.current_path.name, Qt.MatchFlag.MatchExactly
                )
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
        self.profile_label.setText(f"Editing: {path.name}")
        self.editor.setEnabled(True)
        self.editor.setPlainText(source)
        self.editor.document().setModified(False)
        self.save_button.setEnabled(True)

    def _confirm_profile_change(self) -> bool:
        if self.current_path is None or not self.editor.document().isModified():
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
        name, accepted = QInputDialog.getText(self, "New configuration profile", "File name (.yml):")
        if not accepted or not name.strip():
            return
        name = name.strip()
        if not name.endswith(".yml"):
            name += ".yml"
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.yml", name):
            QMessageBox.warning(self, "Invalid name", "Use a simple filename ending in .yml.")
            return
        path = self.config_dir / name
        if path.exists():
            QMessageBox.warning(self, "Already exists", f"{name} already exists.")
            return
        try:
            ConfigService.save_config_yaml(path, "# Espanso configuration profile\n")
        except OSError as error:
            QMessageBox.critical(self, "Create failed", str(error))
            return
        self._load_profiles(path)

    def delete_profile(self) -> None:
        if self.current_path is None:
            return
        if not self._confirm_profile_change():
            return
        path = self.current_path
        if (
            QMessageBox.question(
                self,
                "Delete configuration profile",
                f'Really delete "{path.name}"?',
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
        try:
            ConfigService.save_config_yaml(self.current_path, self.editor.toPlainText())
        except (OSError, ValueError, __import__("yaml").YAMLError) as error:
            QMessageBox.critical(self, "Invalid configuration", str(error))
            return False
        self.editor.document().setModified(False)
        return True

    def reject(self) -> None:
        if self._confirm_profile_change():
            super().reject()


class MainWindow(QMainWindow):
    """The complete editor window and its in-memory document state."""

    def __init__(self) -> None:
        super().__init__()
        self.config_path = ConfigService.detect_config_path()
        self.current_file: Path | None = None
        self.matches: list[EspansoMatch] = []
        self.document_extra: dict[str, object] = {}
        self.selected_match = -1
        self.selected_variable = -1
        self.selected_form_field = ""
        self.dirty = False
        self._loading = False
        self._build_ui()
        self.load_files()
        self._set_editor_enabled(False)

    def _build_ui(self) -> None:
        self.resize(1280, 820)
        self.setWindowTitle(APP_NAME)
        self._load_window_icon()
        self._build_menu()

    def _load_window_icon(self) -> None:
        self.setWindowIcon(application_icon())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_file_panel())
        splitter.addWidget(self._build_editor_panel())
        splitter.setSizes([360, 1040])
        self.setCentralWidget(splitter)
        self.statusBar().showMessage(f"Configuration folder: {self.config_path}")

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("File")
        save = QAction("Save", self)
        save.setShortcut("Ctrl+S")
        save.triggered.connect(self.save_current_file)
        new_config = QAction("New configuration", self)
        new_config.setShortcut("Ctrl+N")
        new_config.triggered.connect(self.new_file)
        expert_yaml = QAction("Expert YAML…", self)
        expert_yaml.setShortcut("Ctrl+E")
        expert_yaml.triggered.connect(self.open_yaml_editor)
        espanso_config = QAction("Espanso configuration…", self)
        espanso_config.triggered.connect(self.open_espanso_configuration)
        menu.addActions([new_config, save, expert_yaml, espanso_config])

        edit_menu = self.menuBar().addMenu("Edit")
        duplicate = QAction("Duplicate match", self)
        duplicate.setShortcut("Ctrl+D")
        duplicate.triggered.connect(self.duplicate_match)
        edit_menu.addAction(duplicate)

        help_menu = self.menuBar().addMenu("Help")
        about = QAction("About Espanso GUI", self)
        about.triggered.connect(lambda: show_about_dialog(self, self.config_path))
        help_menu.addAction(about)

    def _build_file_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QLabel("Configuration files"))
        buttons = QHBoxLayout()
        new_button = QPushButton("New…")
        delete_button = QPushButton("Delete")
        delete_button.setToolTip("Delete the selected configuration file")
        new_button.clicked.connect(self.new_file)
        delete_button.clicked.connect(self.delete_file)
        buttons.addWidget(new_button)
        buttons.addWidget(delete_button)
        layout.addLayout(buttons)
        self.file_tree = MatchFileTreeWidget(self.move_match_to)
        self.file_tree.setHeaderHidden(True)
        self.file_tree.itemSelectionChanged.connect(self.on_file_selected)
        self.file_tree.setMinimumHeight(130)
        layout.addWidget(self.file_tree, 1)

        self.match_sidebar = QGroupBox("Matches")
        match_layout = QVBoxLayout(self.match_sidebar)

        match_buttons = QHBoxLayout()
        self.add_match_btn = QPushButton("New")
        self.duplicate_match_btn = QPushButton("Duplicate")
        self.move_match_btn = QPushButton("Move…")
        self.delete_match_btn = QPushButton("Delete")
        self.add_match_btn.clicked.connect(self.new_match)
        self.duplicate_match_btn.clicked.connect(self.duplicate_match)
        self.move_match_btn.clicked.connect(self.move_match)
        self.delete_match_btn.clicked.connect(self.delete_match)
        match_buttons.addWidget(self.add_match_btn)
        match_buttons.addWidget(self.duplicate_match_btn)
        match_buttons.addWidget(self.move_match_btn)
        match_buttons.addWidget(self.delete_match_btn)
        match_layout.addLayout(match_buttons)

        self.match_filter = QLineEdit()
        self.match_filter.setClearButtonEnabled(True)
        self.match_filter.setPlaceholderText("Filter matches…")
        self.match_filter.setToolTip("Search trigger, type, or content")
        self.match_filter.textChanged.connect(lambda: self.refresh_match_table(keep_selection=True))
        match_layout.addWidget(self.match_filter)

        self.match_table = MatchTableWidget()
        self.match_table.setToolTip("Drag a match onto another configuration file to move it.")
        self.match_table.setHorizontalHeaderLabels(["Trigger", "Type"])
        self.match_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.match_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.match_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.match_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.match_table.itemSelectionChanged.connect(self.on_match_selected)
        self.match_table.setAlternatingRowColors(True)
        self.match_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.match_table.setSortingEnabled(True)
        match_layout.addWidget(self.match_table, 1)
        layout.addWidget(self.match_sidebar, 2)
        return panel

    def _build_editor_panel(self) -> QWidget:
        self.editor = QWidget()
        editor_layout = QVBoxLayout(self.editor)
        editor_layout.setContentsMargins(8, 8, 8, 8)

        self.file_label = QLabel("No file selected")
        editor_layout.addWidget(self.file_label)

        self.editor_content = QWidget()
        content_layout = QVBoxLayout(self.editor_content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.match_editor_box = QFrame()
        self.match_editor_box.setFrameShape(QFrame.Shape.StyledPanel)
        box = QVBoxLayout(self.match_editor_box)

        match_editor_title = QLabel("Edit selected match")
        box.addWidget(match_editor_title)

        basics_box = QGroupBox("Basic settings")
        top_form = QFormLayout(basics_box)

        trigger_widget = QWidget()
        trigger_layout = QVBoxLayout(trigger_widget)
        trigger_layout.setContentsMargins(0, 0, 0, 0)
        trigger_layout.setSpacing(4)
        primary_trigger_row = QHBoxLayout()
        self.trigger_edit = QLineEdit()
        self.trigger_edit.setPlaceholderText("e.g. :hello")
        self.trigger_edit.textChanged.connect(self._on_match_field_changed)
        primary_trigger_row.addWidget(self.trigger_edit)
        self.add_trigger_button = QPushButton("Add trigger")
        self.add_trigger_button.clicked.connect(lambda: self.add_optional_trigger())
        primary_trigger_row.addWidget(self.add_trigger_button)
        trigger_layout.addLayout(primary_trigger_row)
        self.optional_trigger_layout = QVBoxLayout()
        self.optional_trigger_layout.setContentsMargins(0, 0, 0, 0)
        self.optional_trigger_edits: list[tuple[QLineEdit, QWidget]] = []
        trigger_layout.addLayout(self.optional_trigger_layout)
        top_form.addRow("Trigger:", trigger_widget)

        mode_widget = QWidget()
        mode_layout = QHBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        self.radio_replace = QRadioButton("Text replacement")
        self.radio_form = QRadioButton("Form")
        self.radio_replace.setChecked(True)
        self.radio_replace.toggled.connect(self.on_mode_toggled)
        mode_layout.addWidget(self.radio_replace)
        mode_layout.addWidget(self.radio_form)
        mode_layout.addStretch()
        top_form.addRow("Mode:", mode_widget)

        self.word_check = QCheckBox("Expand only on word boundary")
        self.word_check.toggled.connect(self._on_match_field_changed)
        top_form.addRow("Word boundary:", self.word_check)
        box.addWidget(basics_box)

        self.details_tabs = QTabWidget()
        content_widget = QWidget()
        content_page_layout = QVBoxLayout(content_widget)
        content_page_layout.setContentsMargins(0, 0, 0, 0)
        self.content_stack = QStackedWidget()

        # Replace mode container
        self.replace_widget = QWidget()
        replace_layout = QVBoxLayout(self.replace_widget)
        replace_layout.setContentsMargins(0, 0, 0, 0)
        replace_layout.addWidget(QLabel("Replacement text"))
        self.replace_edit = QTextEdit()
        self.replace_edit.setPlaceholderText("Enter replacement text…")
        self.replace_edit.textChanged.connect(self._on_match_field_changed)
        replace_layout.addWidget(self.replace_edit)
        self.content_stack.addWidget(self.replace_widget)

        # Form mode container
        self.form_widget = QWidget()
        form_layout = QVBoxLayout(self.form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.addWidget(QLabel("Layout (use [[field_name]] for input fields)"))
        self.form_layout_edit = QTextEdit()
        self.form_layout_edit.setPlaceholderText("e.g. Hello [[name]], your ticket [[ticket_id]] is ready.")
        self.form_layout_edit.textChanged.connect(self._on_match_field_changed)
        form_layout.addWidget(self.form_layout_edit)

        fields_box = QGroupBox("Form fields")
        fields_layout = QVBoxLayout(fields_box)

        f_top = QHBoxLayout()
        f_top.addStretch()
        self.btn_detect_fields = QPushButton("Detect fields")
        self.btn_detect_fields.setToolTip("Find all [[variables]] in the layout text above")
        self.btn_detect_fields.clicked.connect(self.detect_form_fields)
        f_top.addWidget(self.btn_detect_fields)
        fields_layout.addLayout(f_top)

        self.form_fields_table = QTableWidget(0, 4)
        self.form_fields_table.setHorizontalHeaderLabels(["Field Name", "Type", "Values (for Choice/List)", "Default"])
        self.form_fields_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.form_fields_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.form_fields_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.form_fields_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.form_fields_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.form_fields_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.form_fields_table.itemSelectionChanged.connect(self.on_form_field_selected)
        self.form_fields_table.setAlternatingRowColors(True)
        self.form_fields_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.form_fields_table.setMinimumHeight(130)
        fields_layout.addWidget(self.form_fields_table)

        ff_form = QFormLayout()
        self.field_name_edit = QLineEdit()
        self.field_type_combo = QComboBox()
        self.field_type_combo.addItems(["Text (single-line)", "Text (multiline)", "Choice Box (dropdown)", "List Box"])
        self.field_type_combo.currentTextChanged.connect(self.on_form_field_type_changed)
        self.field_values_edit = QLineEdit()
        self.field_values_edit.setPlaceholderText("Comma-separated values, e.g. Option 1, Option 2, Option 3")
        self.field_values_edit.setEnabled(False)
        self.field_default_edit = QLineEdit()
        self.field_default_edit.setPlaceholderText("Optional default value")

        ff_form.addRow("Field Name:", self.field_name_edit)
        ff_form.addRow("Field Type:", self.field_type_combo)
        self.field_values_label = QLabel("Values:")
        self.field_values_label.setEnabled(False)
        ff_form.addRow(self.field_values_label, self.field_values_edit)
        ff_form.addRow("Default Value:", self.field_default_edit)
        fields_layout.addLayout(ff_form)

        ff_btns = QHBoxLayout()
        self.btn_add_field = QPushButton("Add")
        self.btn_apply_field = QPushButton("Apply")
        self.btn_delete_field = QPushButton("Delete")
        self.btn_apply_field.setEnabled(False)
        self.btn_delete_field.setEnabled(False)
        self.btn_add_field.clicked.connect(self.add_form_field)
        self.btn_apply_field.clicked.connect(self.update_form_field)
        self.btn_delete_field.clicked.connect(self.delete_form_field)
        ff_btns.addWidget(self.btn_add_field)
        ff_btns.addWidget(self.btn_apply_field)
        ff_btns.addWidget(self.btn_delete_field)
        ff_btns.addStretch()
        fields_layout.addLayout(ff_btns)

        form_layout.addWidget(fields_box)
        self.content_stack.addWidget(self.form_widget)
        content_page_layout.addWidget(self.content_stack)
        self.details_tabs.addTab(content_widget, "Content")

        variables_widget = QWidget()
        variables_layout = QVBoxLayout(variables_widget)
        variables_layout.setContentsMargins(0, 0, 0, 0)
        variables_layout.addWidget(QLabel("Variables are evaluated when this match expands."))
        self.variable_table = QTableWidget(0, 3)
        self.variable_table.setHorizontalHeaderLabels(["Name", "Type", "Parameter"])
        self.variable_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.variable_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.variable_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.variable_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.variable_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.variable_table.itemSelectionChanged.connect(self.on_variable_selected)
        self.variable_table.setAlternatingRowColors(True)
        self.variable_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.variable_table.setMinimumHeight(150)
        variables_layout.addWidget(self.variable_table)

        variable_editor_box = QGroupBox("Edit variable")
        variable_editor_layout = QVBoxLayout(variable_editor_box)
        variable_form = QFormLayout()
        self.variable_name = QLineEdit()
        self.variable_type = QComboBox()
        self.variable_type.addItems(["shell", "script", "date", "form", "choice"])
        self.parameter_label = QLabel("cmd:")
        self.variable_parameter = QLineEdit()
        self.variable_type.currentTextChanged.connect(self.update_parameter_label)
        variable_form.addRow("Name:", self.variable_name)
        variable_form.addRow("Type:", self.variable_type)
        variable_form.addRow(self.parameter_label, self.variable_parameter)
        variable_editor_layout.addLayout(variable_form)

        variable_buttons = QHBoxLayout()
        add_variable = QPushButton("Add")
        self.update_variable_button = QPushButton("Apply")
        delete_variable = QPushButton("Delete")
        add_variable.clicked.connect(self.add_variable)
        self.update_variable_button.clicked.connect(self.update_variable)
        delete_variable.clicked.connect(self.delete_variable)
        variable_buttons.addWidget(add_variable)
        variable_buttons.addWidget(self.update_variable_button)
        variable_buttons.addWidget(delete_variable)
        variable_buttons.addStretch()
        variable_editor_layout.addLayout(variable_buttons)
        variables_layout.addWidget(variable_editor_box)
        variables_layout.addStretch()
        self.details_tabs.addTab(variables_widget, "Variables")

        box.addWidget(self.details_tabs, 1)

        scroll_area.setWidget(self.match_editor_box)
        content_layout.addWidget(scroll_area, 1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        self.save_btn = QPushButton("Save")
        self.restart_btn = QPushButton("Restart Espanso")
        self.save_btn.clicked.connect(self.save_current_file)
        self.restart_btn.clicked.connect(self.restart_espanso)
        bottom.addWidget(self.save_btn)
        bottom.addWidget(self.restart_btn)
        content_layout.addLayout(bottom)

        editor_layout.addWidget(self.editor_content, 1)
        return self.editor

    def _set_editor_enabled(self, enabled: bool) -> None:
        self.editor_content.setEnabled(enabled)
        self.match_sidebar.setEnabled(enabled)
        if not enabled:
            self.file_label.setText("No file selected")
            self.match_sidebar.setTitle("Matches")
            self.setWindowTitle(APP_NAME)

    def _on_match_field_changed(self) -> None:
        if not self._loading and 0 <= self.selected_match < len(self.matches):
            self.dirty = True

    def load_files(self, selected_path: Path | None = None) -> None:
        self.file_tree.blockSignals(True)
        self.file_tree.clear()
        root = QTreeWidgetItem(["Configs"])
        root.setData(0, Qt.ItemDataRole.UserRole, None)
        self.file_tree.addTopLevelItem(root)
        if self.config_path.is_dir():
            for path in sorted(self.config_path.glob("*.yml"), key=lambda p: p.name.lower()):
                item = QTreeWidgetItem([path.name])
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                root.addChild(item)
                if path == selected_path:
                    self.file_tree.setCurrentItem(item)
        root.setExpanded(True)
        self.file_tree.blockSignals(False)

    def _ask_save_changes(self) -> bool:
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            "Save changes before continuing?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return answer != QMessageBox.StandardButton.Yes or self.save_current_file()

    def on_file_selected(self) -> None:
        selected = self.file_tree.selectedItems()
        if not selected:
            return
        path = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(path, Path) or path == self.current_file:
            return
        if not self._ask_save_changes():
            self.file_tree.blockSignals(True)
            self.file_tree.clearSelection()
            self.file_tree.blockSignals(False)
            return
        self.load_file(path)

    def load_file(self, path: Path) -> None:
        try:
            self.matches, self.document_extra = ConfigService.parse_yaml_document(path)
        except (OSError, ValueError, __import__("yaml").YAMLError) as error:
            QMessageBox.critical(self, "Parse error", f"Could not load {path.name}:\n{error}")
            return
        self.current_file = path
        self.dirty = False
        self.selected_match = -1
        self.file_label.setText(f"File: {path.name}")
        self.match_sidebar.setTitle(f"Matches — {path.name}")
        self.setWindowTitle(f"{APP_NAME} — {path.name}")
        self._set_editor_enabled(True)
        self.refresh_match_table()
        if self.matches:
            self._select_match(0)
        else:
            self.clear_match_form()
            self.match_editor_box.setEnabled(False)
            self.delete_match_btn.setEnabled(False)

    def new_file(self) -> None:
        name, accepted = QInputDialog.getText(self, "New configuration", "File name (.yml):")
        if not accepted or not name.strip():
            return
        name = name.strip()
        if not name.endswith(".yml"):
            name += ".yml"
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.yml", name):
            QMessageBox.warning(self, "Invalid name", "Use a simple filename ending in .yml.")
            return
        path = self.config_path / name
        if path.exists():
            QMessageBox.warning(self, "Already exists", f"{name} already exists.")
            return
        try:
            ConfigService.save_yaml(path, [])
        except OSError as error:
            QMessageBox.critical(self, "Create failed", str(error))
            return
        self.load_files()
        self.load_file(path)

    def delete_file(self) -> None:
        selected = self.file_tree.selectedItems()
        if not selected or not isinstance(selected[0].data(0, Qt.ItemDataRole.UserRole), Path):
            return
        path: Path = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if (
            QMessageBox.question(
                self,
                "Delete configuration",
                f'Really delete "{path.name}"?',
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
        if path == self.current_file:
            self.current_file = None
            self.matches = []
            self.document_extra = {}
            self.dirty = False
            self._set_editor_enabled(False)
        self.load_files()

    def open_yaml_editor(self) -> None:
        """Open the complete YAML file for advanced Espanso options."""
        if self.current_file is None:
            return
        if not self._ask_save_changes():
            return
        try:
            source = self.current_file.read_text(encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(self, "Open failed", str(error))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Expert YAML — {self.current_file.name}")
        dialog.resize(900, 650)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Edit the full Espanso YAML document. It is validated before saving."))
        editor = QPlainTextEdit()
        editor.setPlainText(source)
        editor.setTabStopDistance(editor.fontMetrics().horizontalAdvance(" ") * 2)
        layout.addWidget(editor, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.rejected.connect(dialog.reject)

        def save_expert_yaml() -> None:
            path = self.current_file
            try:
                ConfigService.save_raw_yaml(path, editor.toPlainText())
                self.load_files(selected_path=path)
                self.load_file(path)
            except (OSError, ValueError, __import__("yaml").YAMLError) as error:
                QMessageBox.critical(dialog, "Invalid YAML", str(error))
                return
            self.statusBar().showMessage(f"Saved {self.current_file.name}", 4000)
            dialog.accept()

        buttons.accepted.connect(save_expert_yaml)
        layout.addWidget(buttons)
        dialog.exec()

    def open_espanso_configuration(self) -> None:
        """Open Espanso's config directory without mixing profiles with match files."""
        if not self._ask_save_changes():
            return
        dialog = EspansoConfigDialog(self)
        dialog.exec()

    def persist_current_match(self) -> None:
        if self._loading or not (0 <= self.selected_match < len(self.matches)):
            return
        match = self.matches[self.selected_match]
        trigger_values = [self.trigger_edit.text().strip()]
        trigger_values.extend(edit.text().strip() for edit, _ in self.optional_trigger_edits)
        match.set_trigger_values(trigger_values, preserve_multiple=bool(match.triggers))
        match.word = self.word_check.isChecked()
        if self.radio_form.isChecked():
            match.mode = "form"
            match.form = self.form_layout_edit.toPlainText()
            match.replace = ""
        else:
            match.mode = "replace"
            match.replace = self.replace_edit.toPlainText()
            match.form = ""

    def add_optional_trigger(self, text: str = "") -> None:
        """Add an editable alias for the currently selected match."""
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        trigger_edit = QLineEdit(text)
        trigger_edit.setPlaceholderText("Additional trigger")
        trigger_edit.textChanged.connect(self._on_match_field_changed)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(lambda: self.remove_optional_trigger(row_widget))
        row.addWidget(trigger_edit)
        row.addWidget(remove_button)
        self.optional_trigger_edits.append((trigger_edit, row_widget))
        self.optional_trigger_layout.addWidget(row_widget)

    def remove_optional_trigger(self, row_widget: QWidget) -> None:
        self.optional_trigger_edits = [
            entry for entry in self.optional_trigger_edits if entry[1] is not row_widget
        ]
        self.optional_trigger_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        self._on_match_field_changed()

    def clear_optional_triggers(self) -> None:
        for _, row_widget in self.optional_trigger_edits:
            self.optional_trigger_layout.removeWidget(row_widget)
            row_widget.deleteLater()
        self.optional_trigger_edits.clear()

    def new_match(self) -> None:
        self.persist_current_match()
        self.matches.append(EspansoMatch(trigger=":new"))
        self.dirty = True
        self.refresh_match_table()
        row = len(self.matches) - 1
        self._select_match(row)
        self.trigger_edit.setFocus()
        self.trigger_edit.selectAll()

    def duplicate_match(self) -> None:
        if not (0 <= self.selected_match < len(self.matches)):
            return
        import copy

        self.persist_current_match()
        original = self.matches[self.selected_match]
        duplicate = copy.deepcopy(original)
        if original.triggers:
            duplicate.triggers = [f"{trigger}_copy" for trigger in original.triggers]
        else:
            duplicate.trigger = f"{original.trigger}_copy"
        self.matches.insert(self.selected_match + 1, duplicate)
        self.dirty = True
        self.refresh_match_table()
        self._select_match(self.selected_match + 1)

    def move_match(self) -> None:
        """Move the selected match to another Espanso match configuration file."""
        if self.current_file is None or not (0 <= self.selected_match < len(self.matches)):
            return

        source_path = self.current_file
        destinations = [
            path for path in sorted(self.config_path.glob("*.yml"), key=lambda path: path.name.lower())
            if path != source_path
        ]
        if not destinations:
            QMessageBox.information(
                self,
                "Move match",
                "Create another configuration file before moving a match.",
            )
            return
        destination_path = choose_match_destination(self, destinations)
        if destination_path is None:
            return

        self.move_match_to(destination_path, self.selected_match)

    def move_match_to(self, destination_path: Path, source_index: int) -> None:
        """Persist and move a match selected through the dialog or a drag operation."""
        if (
            self.current_file is None
            or destination_path == self.current_file
            or not (0 <= source_index < len(self.matches))
        ):
            return

        source_path = self.current_file
        self.persist_current_match()
        moved_match = self.matches[source_index]
        removed_from_source = False
        try:
            destination_matches, destination_extra = ConfigService.parse_yaml_document(destination_path)
            destination_matches.append(moved_match)
            ConfigService.save_yaml(destination_path, destination_matches, destination_extra)
            del self.matches[source_index]
            removed_from_source = True
            ConfigService.save_yaml(source_path, self.matches, self.document_extra)
        except (OSError, ValueError, __import__("yaml").YAMLError) as error:
            if removed_from_source:
                self.matches.insert(source_index, moved_match)
            QMessageBox.critical(self, "Move failed", f"Could not move the match:\n{error}")
            return

        self.load_files(selected_path=source_path)
        self.load_file(source_path)
        self.statusBar().showMessage(f"Moved match to {destination_path.name}", 4000)

    def delete_match(self) -> None:
        if not (0 <= self.selected_match < len(self.matches)):
            return
        if (
            QMessageBox.question(
                self,
                "Delete match",
                "Really delete this match?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        del self.matches[self.selected_match]
        self.selected_match = -1
        self.dirty = True
        self.refresh_match_table()
        if self.matches:
            self._select_match(0)
        else:
            self.clear_match_form()
            self.match_editor_box.setEnabled(False)
            self.delete_match_btn.setEnabled(False)

    def refresh_match_table(self, keep_selection: bool = False) -> None:
        self._loading = True
        prev_row = self.selected_match if keep_selection else -1
        query = self.match_filter.text().strip().casefold()
        visible_matches = [
            (index, match) for index, match in enumerate(self.matches)
            if not query or query in f"{match.trigger_text} {'Form' if match.is_form else 'Replace'} {match.preview}".casefold()
        ]
        self.match_table.setSortingEnabled(False)
        self.match_table.setRowCount(len(visible_matches))
        for row, (index, match) in enumerate(visible_matches):
            type_str = "Form" if match.is_form else "Replace"
            for column, value in enumerate((match.trigger_text, type_str)):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.match_table.setItem(row, column, item)
        self.match_table.setSortingEnabled(True)
        if 0 <= prev_row < len(self.matches):
            self._select_match(prev_row)
        self._loading = False

    def _select_match(self, match_index: int) -> None:
        for row in range(self.match_table.rowCount()):
            item = self.match_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == match_index:
                self.match_table.selectRow(row)
                return

    def on_mode_toggled(self) -> None:
        is_form = self.radio_form.isChecked()
        self.content_stack.setCurrentIndex(1 if is_form else 0)
        self.details_tabs.setCurrentIndex(0)
        if not self._loading and 0 <= self.selected_match < len(self.matches):
            # A new mode starts empty; hidden editors must not restore old text.
            self._loading = True
            self.replace_edit.clear()
            self.form_layout_edit.clear()
            self._loading = False
            self.persist_current_match()
            self.dirty = True
            self.refresh_match_table(keep_selection=True)

    def on_match_selected(self) -> None:
        if self._loading:
            return
        self.persist_current_match()
        rows = self.match_table.selectionModel().selectedRows()
        if not rows:
            self.selected_match = -1
            self.match_editor_box.setEnabled(False)
            self.delete_match_btn.setEnabled(False)
            return
        item = self.match_table.item(rows[0].row(), 0)
        if item is None:
            return
        self.selected_match = item.data(Qt.ItemDataRole.UserRole)
        self.selected_variable = -1
        self.selected_form_field = ""
        self.match_editor_box.setEnabled(True)
        self.delete_match_btn.setEnabled(True)
        match = self.matches[self.selected_match]

        self._loading = True
        self.clear_optional_triggers()
        if match.triggers:
            self.trigger_edit.setText(match.triggers[0] if match.triggers else "")
            for trigger in match.triggers[1:]:
                self.add_optional_trigger(trigger)
        else:
            self.trigger_edit.setText(match.trigger)
        self.word_check.setChecked(match.word)
        # Refresh hidden content too, so it cannot leak between matches.
        self.replace_edit.setPlainText(match.replace)
        self.form_layout_edit.setPlainText(match.form)
        if match.is_form:
            self.radio_form.setChecked(True)
            self.content_stack.setCurrentIndex(1)
        else:
            self.radio_replace.setChecked(True)
            self.content_stack.setCurrentIndex(0)
        self._loading = False

        self.refresh_form_fields_table()
        self.clear_form_field_form()
        self.refresh_variable_table()
        self.clear_variable_form()

    def clear_match_form(self) -> None:
        self._loading = True
        self.trigger_edit.clear()
        self.clear_optional_triggers()
        self.replace_edit.clear()
        self.form_layout_edit.clear()
        self.radio_replace.setChecked(True)
        self.content_stack.setCurrentIndex(0)
        self.details_tabs.setCurrentIndex(0)
        self.word_check.setChecked(False)
        self._loading = False
        self.refresh_form_fields_table()
        self.clear_form_field_form()
        self.refresh_variable_table()
        self.clear_variable_form()

    def detect_form_fields(self) -> None:
        if not (0 <= self.selected_match < len(self.matches)):
            return
        match = self.matches[self.selected_match]
        layout_text = self.form_layout_edit.toPlainText()
        match.form = layout_text
        detected = match.detect_field_names()
        added_any = False
        for name in detected:
            if name not in match.form_fields:
                match.form_fields[name] = EspansoFormField(name=name, type="text")
                added_any = True
        if added_any:
            self.dirty = True
        self.refresh_form_fields_table()

    def refresh_form_fields_table(self) -> None:
        self.form_fields_table.setRowCount(0)
        if not (0 <= self.selected_match < len(self.matches)):
            return
        match = self.matches[self.selected_match]
        layout_vars = match.detect_field_names()
        for var_name in layout_vars:
            if var_name not in match.form_fields:
                match.form_fields[var_name] = EspansoFormField(name=var_name, type="text")

        self.form_fields_table.setRowCount(len(match.form_fields))
        for row, (name, field_obj) in enumerate(match.form_fields.items()):
            type_desc = field_obj.type
            if field_obj.type == "choice":
                type_desc = "Choice Box"
            elif field_obj.type == "list":
                type_desc = "List Box"
            elif field_obj.multiline:
                type_desc = "Text (multiline)"
            else:
                type_desc = "Text (single-line)"
            values_desc = ", ".join(field_obj.values) if field_obj.values else ""
            self.form_fields_table.setItem(row, 0, QTableWidgetItem(name))
            self.form_fields_table.setItem(row, 1, QTableWidgetItem(type_desc))
            self.form_fields_table.setItem(row, 2, QTableWidgetItem(values_desc))
            self.form_fields_table.setItem(row, 3, QTableWidgetItem(field_obj.default))

    def on_form_field_selected(self) -> None:
        rows = self.form_fields_table.selectionModel().selectedRows()
        if not rows or not (0 <= self.selected_match < len(self.matches)):
            return
        row = rows[0].row()
        name_item = self.form_fields_table.item(row, 0)
        if not name_item:
            return
        name = name_item.text()
        match = self.matches[self.selected_match]
        field_obj = match.form_fields.get(name)
        if not field_obj:
            return
        self.selected_form_field = name
        self.field_name_edit.setText(field_obj.name)
        if field_obj.type == "choice":
            self.field_type_combo.setCurrentText("Choice Box (dropdown)")
        elif field_obj.type == "list":
            self.field_type_combo.setCurrentText("List Box")
        elif field_obj.multiline:
            self.field_type_combo.setCurrentText("Text (multiline)")
        else:
            self.field_type_combo.setCurrentText("Text (single-line)")
        self.field_values_edit.setText(", ".join(field_obj.values))
        self.field_default_edit.setText(field_obj.default)
        self.btn_apply_field.setEnabled(True)
        self.btn_delete_field.setEnabled(True)

    def on_form_field_type_changed(self, text: str) -> None:
        is_choice_or_list = "Choice" in text or "List" in text
        self.field_values_edit.setEnabled(is_choice_or_list)
        self.field_values_label.setEnabled(is_choice_or_list)

    def _form_field_from_inputs(self, name: str) -> EspansoFormField:
        type_text = self.field_type_combo.currentText()
        field_type = "text"
        multiline = False
        if "Choice" in type_text:
            field_type = "choice"
        elif "List" in type_text:
            field_type = "list"
        elif "multiline" in type_text:
            multiline = True

        raw_values = self.field_values_edit.text().strip()
        values = [v.strip() for v in raw_values.split(",") if v.strip()] if raw_values else []
        default_val = self.field_default_edit.text().strip()
        return EspansoFormField(
            name=name,
            type=field_type,
            multiline=multiline,
            values=values,
            default=default_val,
        )

    def add_form_field(self) -> None:
        if not (0 <= self.selected_match < len(self.matches)):
            return
        name = self.field_name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Field name", "Please enter a field name.")
            self.field_name_edit.setFocus()
            return
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
            QMessageBox.warning(self, "Invalid name", "Field names may only contain letters, numbers, and underscores.")
            return
        match = self.matches[self.selected_match]
        field_obj = self._form_field_from_inputs(name)
        match.form_fields[name] = field_obj
        self.dirty = True
        self.refresh_form_fields_table()
        self.clear_form_field_form()

    def update_form_field(self) -> None:
        if not (0 <= self.selected_match < len(self.matches)) or not self.selected_form_field:
            return
        name = self.field_name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Field name", "Please enter a field name.")
            return
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
            QMessageBox.warning(self, "Invalid name", "Field names may only contain letters, numbers, and underscores.")
            return
        match = self.matches[self.selected_match]
        if name != self.selected_form_field and self.selected_form_field in match.form_fields:
            del match.form_fields[self.selected_form_field]
        field_obj = self._form_field_from_inputs(name)
        match.form_fields[name] = field_obj
        self.dirty = True
        self.refresh_form_fields_table()

    def delete_form_field(self) -> None:
        if not (0 <= self.selected_match < len(self.matches)) or not self.selected_form_field:
            return
        if (
            QMessageBox.question(
                self,
                "Delete field",
                f"Really delete field '{self.selected_form_field}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        match = self.matches[self.selected_match]
        if self.selected_form_field in match.form_fields:
            del match.form_fields[self.selected_form_field]
            self.dirty = True
            self.refresh_form_fields_table()
            self.clear_form_field_form()

    def clear_form_field_form(self) -> None:
        self.selected_form_field = ""
        self.field_name_edit.clear()
        self.field_type_combo.setCurrentIndex(0)
        self.field_values_edit.clear()
        self.field_default_edit.clear()
        self.field_values_edit.setEnabled(False)
        self.field_values_label.setEnabled(False)
        self.btn_apply_field.setEnabled(False)
        self.btn_delete_field.setEnabled(False)

    def refresh_variable_table(self) -> None:
        self.variable_table.setRowCount(0)
        if not (0 <= self.selected_match < len(self.matches)):
            return
        variables = self.matches[self.selected_match].variables
        self.variable_table.setRowCount(len(variables))
        for row, variable in enumerate(variables):
            self.variable_table.setItem(row, 0, QTableWidgetItem(variable.name))
            self.variable_table.setItem(row, 1, QTableWidgetItem(variable.type))
            self.variable_table.setItem(row, 2, QTableWidgetItem(variable.parameter_value))

    def clear_variable_form(self) -> None:
        self.selected_variable = -1
        self.variable_name.clear()
        self.variable_type.setCurrentText("shell")
        self.variable_parameter.clear()
        self.update_variable_button.setEnabled(False)

    def update_parameter_label(self, variable_type: str) -> None:
        labels = {
            "shell": "cmd:", "script": "path:", "date": "format:", "form": "layout:",
            "choice": "choices:",
        }
        self.parameter_label.setText(labels.get(variable_type, "param:"))
        self.variable_parameter.setPlaceholderText(
            "Comma-separated choices, e.g. yes, no" if variable_type == "choice" else ""
        )

    def _variable_from_form(self, existing: EspansoVariable | None = None) -> EspansoVariable | None:
        name = self.variable_name.text().strip()
        if not name:
            QMessageBox.information(self, "Variable name", "Please enter a variable name.")
            self.variable_name.setFocus()
            return None
        variable = existing or EspansoVariable()
        variable.name = name
        variable.type = self.variable_type.currentText()
        variable.set_parameter_value(self.variable_parameter.text())
        return variable

    def add_variable(self) -> None:
        if not (0 <= self.selected_match < len(self.matches)):
            return
        variable = self._variable_from_form()
        if variable is None:
            return
        self.matches[self.selected_match].variables.append(variable)
        self.dirty = True
        self.refresh_variable_table()
        self.clear_variable_form()

    def on_variable_selected(self) -> None:
        rows = self.variable_table.selectionModel().selectedRows()
        if not rows or not (0 <= self.selected_match < len(self.matches)):
            return
        self.selected_variable = rows[0].row()
        variable = self.matches[self.selected_match].variables[self.selected_variable]
        self.variable_name.setText(variable.name)
        self.variable_type.setCurrentText(variable.type)
        self.variable_parameter.setText(variable.parameter_value)
        self.update_variable_button.setEnabled(True)

    def update_variable(self) -> None:
        if not (0 <= self.selected_match < len(self.matches) and 0 <= self.selected_variable < len(self.matches[self.selected_match].variables)):
            return
        variable = self._variable_from_form(self.matches[self.selected_match].variables[self.selected_variable])
        if variable is None:
            return
        self.dirty = True
        self.refresh_variable_table()
        self.variable_table.selectRow(self.selected_variable)

    def delete_variable(self) -> None:
        if not (0 <= self.selected_match < len(self.matches) and 0 <= self.selected_variable < len(self.matches[self.selected_match].variables)):
            return
        if (
            QMessageBox.question(
                self,
                "Delete variable",
                "Really delete this variable?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        del self.matches[self.selected_match].variables[self.selected_variable]
        self.dirty = True
        self.refresh_variable_table()
        self.clear_variable_form()

    def save_current_file(self) -> bool:
        if self.current_file is None:
            return False
        self.persist_current_match()
        try:
            ConfigService.save_yaml(self.current_file, self.matches, self.document_extra)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Save error", f"Could not save {self.current_file.name}:\n{error}")
            return False
        self.dirty = False
        self.refresh_match_table(keep_selection=True)
        self.statusBar().showMessage(f"Saved {self.current_file.name}", 4000)
        return True

    def restart_espanso(self) -> None:
        try:
            result = ConfigService.restart_espanso()
        except (OSError, TimeoutError) as error:
            QMessageBox.critical(self, "Restart failed", f"Could not run espanso:\n{error}")
            return
        if result.returncode == 0:
            QMessageBox.information(self, "Espanso restarted", "Espanso has been restarted.")
        else:
            detail = result.stderr.strip() or result.stdout.strip() or f"Exit code {result.returncode}"
            QMessageBox.warning(self, "Restart failed", detail)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._ask_save_changes():
            event.accept()
        else:
            event.ignore()


def main() -> int:
    setup_qt_environment()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(application_icon())

    # If the user did not specify -style / --style via command line, apply desktop style
    has_cli_style = any(arg in sys.argv for arg in ("-style", "--style"))
    if not has_cli_style:
        preferred_style = _detect_desktop_style()
        available_styles = {k.lower(): k for k in QStyleFactory.keys()}

        if preferred_style and preferred_style.lower() in available_styles:
            target_name = available_styles[preferred_style.lower()]
            if app.style().objectName().lower() != target_name.lower():
                app.setStyle(target_name)
        elif "breeze" in available_styles:
            current_style = app.style().objectName().lower()
            if current_style in ("fusion", "windows"):
                app.setStyle(available_styles["breeze"])

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
