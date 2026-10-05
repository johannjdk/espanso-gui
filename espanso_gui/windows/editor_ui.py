"""WindowLayoutMixin."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..ui.match_drag_drop import MatchFileTreeWidget, MatchTableWidget


class ParameterStack(QStackedWidget):
    """Stacked widget that adjusts its size hint to match the active page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.currentChanged.connect(self._on_current_changed)

    def _on_current_changed(self, index: int) -> None:
        widget = self.widget(index)
        if widget is not None:
            self.setSizePolicy(widget.sizePolicy())
            self.updateGeometry()

    def sizeHint(self):
        widget = self.currentWidget()
        return widget.sizeHint() if widget is not None else super().sizeHint()

    def minimumSizeHint(self):
        widget = self.currentWidget()
        return widget.minimumSizeHint() if widget is not None else super().minimumSizeHint()


class WindowLayoutMixin:
    def _build_file_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QLabel("Configuration files"))
        search_button = QPushButton("Search all configurations…")
        search_button.setToolTip("Search all match files (Ctrl+F)")
        search_button.clicked.connect(self.search_all_configurations)
        layout.addWidget(search_button)
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

        self.match_table = MatchTableWidget(0, 2)
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
        self.regex_check = QCheckBox("Regex")
        self.regex_check.setToolTip("Match trigger as a regular expression")
        self.regex_check.toggled.connect(self.on_regex_toggled)
        primary_trigger_row.addWidget(self.regex_check)
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
        variable_editor_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        variable_editor_layout = QVBoxLayout(variable_editor_box)
        variable_form = QFormLayout()
        self.variable_name = QLineEdit()
        self.variable_type = QComboBox()
        self.variable_type.addItems(["shell", "script", "date", "form", "choice"])
        self.parameter_label = QLabel("cmd:")
        self.parameter_stack = ParameterStack()
        self.variable_parameter = QLineEdit()
        self.variable_layout_edit = QPlainTextEdit()
        self.variable_layout_edit.setPlaceholderText("Form layout template, e.g.:\nLine 1: [[field1]]\nLine 2: [[field2]]")
        self.variable_layout_edit.setMinimumHeight(70)
        self.parameter_stack.addWidget(self.variable_parameter)
        self.parameter_stack.addWidget(self.variable_layout_edit)
        self.variable_type.currentTextChanged.connect(self.update_parameter_label)
        variable_form.addRow("Name:", self.variable_name)
        variable_form.addRow("Type:", self.variable_type)
        variable_form.addRow(self.parameter_label, self.parameter_stack)
        variable_editor_layout.addLayout(variable_form)

        self.var_fields_box = QGroupBox("Form fields")
        var_fields_layout = QVBoxLayout(self.var_fields_box)

        vf_top = QHBoxLayout()
        vf_top.addStretch()
        self.btn_detect_var_fields = QPushButton("Detect fields")
        self.btn_detect_var_fields.setToolTip("Find all [[variables]] in the layout text above")
        self.btn_detect_var_fields.clicked.connect(self.detect_var_fields)
        vf_top.addWidget(self.btn_detect_var_fields)
        var_fields_layout.addLayout(vf_top)

        self.var_fields_table = QTableWidget(0, 4)
        self.var_fields_table.setHorizontalHeaderLabels(["Field Name", "Type", "Values (for Choice/List)", "Default"])
        self.var_fields_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.var_fields_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.var_fields_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.var_fields_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.var_fields_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.var_fields_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.var_fields_table.itemSelectionChanged.connect(self.on_var_field_selected)
        self.var_fields_table.setAlternatingRowColors(True)
        self.var_fields_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.var_fields_table.setMinimumHeight(120)
        var_fields_layout.addWidget(self.var_fields_table)

        vf_form = QFormLayout()
        self.var_field_name_edit = QLineEdit()
        self.var_field_type_combo = QComboBox()
        self.var_field_type_combo.addItems(["Text (single-line)", "Text (multiline)", "Choice Box (dropdown)", "List Box"])
        self.var_field_type_combo.currentTextChanged.connect(self.on_var_field_type_changed)
        self.var_field_values_edit = QLineEdit()
        self.var_field_values_edit.setPlaceholderText("Comma-separated values, e.g. Option 1, Option 2, Option 3")
        self.var_field_values_edit.setEnabled(False)
        self.var_field_default_edit = QLineEdit()
        self.var_field_default_edit.setPlaceholderText("Optional default value")

        vf_form.addRow("Field Name:", self.var_field_name_edit)
        vf_form.addRow("Field Type:", self.var_field_type_combo)
        self.var_field_values_label = QLabel("Values:")
        self.var_field_values_label.setEnabled(False)
        vf_form.addRow(self.var_field_values_label, self.var_field_values_edit)
        vf_form.addRow("Default Value:", self.var_field_default_edit)
        var_fields_layout.addLayout(vf_form)

        vf_btns = QHBoxLayout()
        self.btn_add_var_field = QPushButton("Add field")
        self.btn_apply_var_field = QPushButton("Apply field")
        self.btn_delete_var_field = QPushButton("Delete field")
        self.btn_apply_var_field.setEnabled(False)
        self.btn_delete_var_field.setEnabled(False)
        self.btn_add_var_field.clicked.connect(self.add_var_field)
        self.btn_apply_var_field.clicked.connect(self.update_var_field)
        self.btn_delete_var_field.clicked.connect(self.delete_var_field)
        vf_btns.addWidget(self.btn_add_var_field)
        vf_btns.addWidget(self.btn_apply_var_field)
        vf_btns.addWidget(self.btn_delete_var_field)
        vf_btns.addStretch()
        var_fields_layout.addLayout(vf_btns)

        self.var_fields_box.hide()
        variable_editor_layout.addWidget(self.var_fields_box)

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
