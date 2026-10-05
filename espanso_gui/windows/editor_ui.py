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
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..ui.match_drag_drop import MatchFileTreeWidget, MatchTableWidget




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
        variables_layout.setContentsMargins(6, 6, 6, 6)

        self.variables_splitter = QSplitter(Qt.Orientation.Horizontal)

        var_list_panel = QWidget()
        var_list_layout = QVBoxLayout(var_list_panel)
        var_list_layout.setContentsMargins(0, 0, 0, 0)
        var_list_layout.setSpacing(6)

        var_list_layout.addWidget(QLabel("Variables"))

        self.variable_table = QTableWidget(0, 2)
        self.variable_table.setHorizontalHeaderLabels(["Name", "Type"])
        self.variable_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.variable_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.variable_table.verticalHeader().setVisible(False)
        self.variable_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.variable_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.variable_table.setAlternatingRowColors(True)
        self.variable_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.variable_table.itemSelectionChanged.connect(self.on_variable_selected)
        var_list_layout.addWidget(self.variable_table, 1)

        var_btn_layout = QHBoxLayout()
        self.btn_add_variable = QPushButton("Add Variable")
        self.btn_delete_variable = QPushButton("Delete")
        self.btn_delete_variable.setEnabled(False)
        self.btn_add_variable.clicked.connect(self.add_variable)
        self.btn_delete_variable.clicked.connect(self.delete_variable)
        var_btn_layout.addWidget(self.btn_add_variable)
        var_btn_layout.addWidget(self.btn_delete_variable)
        var_list_layout.addLayout(var_btn_layout)

        self.variables_splitter.addWidget(var_list_panel)

        self.var_config_stack = QStackedWidget()

        var_placeholder = QWidget()
        placeholder_layout = QVBoxLayout(var_placeholder)
        placeholder_layout.setContentsMargins(16, 16, 16, 16)
        placeholder_label = QLabel("No variable selected.\nSelect a variable or click 'Add Variable' to configure it.")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(placeholder_label)
        self.var_config_stack.addWidget(var_placeholder)

        var_scroll_area = QScrollArea()
        var_scroll_area.setWidgetResizable(True)
        var_scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        var_detail_panel = QWidget()
        var_detail_layout = QVBoxLayout(var_detail_panel)
        var_detail_layout.setContentsMargins(6, 0, 6, 6)
        var_detail_layout.setSpacing(10)

        var_form = QFormLayout()
        self.variable_name = QLineEdit()
        self.variable_name.setPlaceholderText("e.g. my_var")
        self.variable_name.textChanged.connect(self.on_variable_name_changed)

        self.variable_type = QComboBox()
        self.variable_type.addItems(["shell", "form", "script", "choice", "date"])
        self.variable_type.currentTextChanged.connect(self.on_variable_type_changed)

        var_form.addRow("Variable name:", self.variable_name)
        var_form.addRow("Type:", self.variable_type)
        var_detail_layout.addLayout(var_form)

        self.param_stack = QStackedWidget()

        # Page 0: shell
        shell_widget = QWidget()
        shell_layout = QFormLayout(shell_widget)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        self.var_shell_edit = QLineEdit()
        self.var_shell_edit.setPlaceholderText("e.g. echo Hello World")
        self.var_shell_edit.textChanged.connect(self.on_variable_parameter_changed)
        shell_layout.addRow("Command (cmd):", self.var_shell_edit)
        self.param_stack.addWidget(shell_widget)

        # Page 1: form
        form_var_widget = QWidget()
        form_var_layout = QVBoxLayout(form_var_widget)
        form_var_layout.setContentsMargins(0, 0, 0, 0)
        form_var_layout.setSpacing(8)

        layout_label_row = QHBoxLayout()
        layout_label_row.addWidget(QLabel("Form layout template:"))
        layout_label_row.addStretch()
        self.btn_detect_var_fields = QPushButton("Detect fields")
        self.btn_detect_var_fields.setToolTip("Find [[field]] placeholders in the layout text")
        self.btn_detect_var_fields.clicked.connect(self.detect_var_fields)
        layout_label_row.addWidget(self.btn_detect_var_fields)
        form_var_layout.addLayout(layout_label_row)

        self.variable_layout_edit = QPlainTextEdit()
        self.variable_layout_edit.setPlaceholderText("Form layout template, e.g.:\nEnter name: [[name]]\nSelect role: [[role]]")
        self.variable_layout_edit.setMinimumHeight(75)
        self.variable_layout_edit.setMaximumHeight(130)
        self.variable_layout_edit.textChanged.connect(self.on_variable_layout_changed)
        form_var_layout.addWidget(self.variable_layout_edit)

        self.var_fields_box = QGroupBox("Form fields")
        var_fields_layout = QVBoxLayout(self.var_fields_box)
        var_fields_layout.setSpacing(6)

        self.var_fields_table = QTableWidget(0, 4)
        self.var_fields_table.setHorizontalHeaderLabels(["Field Name", "Type", "Values (for Choice/List)", "Default"])
        self.var_fields_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.var_fields_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.var_fields_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.var_fields_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.var_fields_table.verticalHeader().setVisible(False)
        self.var_fields_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.var_fields_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.var_fields_table.setAlternatingRowColors(True)
        self.var_fields_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.var_fields_table.setMinimumHeight(100)
        self.var_fields_table.itemSelectionChanged.connect(self.on_var_field_selected)
        var_fields_layout.addWidget(self.var_fields_table)

        self.var_field_form_widget = QWidget()
        vf_form = QFormLayout(self.var_field_form_widget)
        vf_form.setContentsMargins(0, 4, 0, 4)
        self.var_field_name_edit = QLineEdit()
        self.var_field_name_edit.editingFinished.connect(self.on_var_field_name_editing_finished)
        self.var_field_type_combo = QComboBox()
        self.var_field_type_combo.addItems(["Text (single-line)", "Text (multiline)", "Choice Box (dropdown)", "List Box"])
        self.var_field_type_combo.currentTextChanged.connect(self.on_var_field_type_changed)
        self.var_field_values_label = QLabel("Values:")
        self.var_field_values_label.setEnabled(False)
        self.var_field_values_edit = QLineEdit()
        self.var_field_values_edit.setPlaceholderText("Comma-separated values, e.g. Option 1, Option 2, Option 3")
        self.var_field_values_edit.setEnabled(False)
        self.var_field_values_edit.textChanged.connect(self.on_var_field_input_changed)
        self.var_field_default_edit = QLineEdit()
        self.var_field_default_edit.setPlaceholderText("Optional default value")
        self.var_field_default_edit.textChanged.connect(self.on_var_field_input_changed)

        vf_form.addRow("Field Name:", self.var_field_name_edit)
        vf_form.addRow("Field Type:", self.var_field_type_combo)
        vf_form.addRow(self.var_field_values_label, self.var_field_values_edit)
        vf_form.addRow("Default Value:", self.var_field_default_edit)
        var_fields_layout.addWidget(self.var_field_form_widget)

        vf_btns = QHBoxLayout()
        self.btn_add_var_field = QPushButton("Add Field")
        self.btn_delete_var_field = QPushButton("Delete Field")
        self.btn_delete_var_field.setEnabled(False)
        self.btn_add_var_field.clicked.connect(self.add_var_field)
        self.btn_delete_var_field.clicked.connect(self.delete_var_field)
        vf_btns.addWidget(self.btn_add_var_field)
        vf_btns.addWidget(self.btn_delete_var_field)
        vf_btns.addStretch()
        var_fields_layout.addLayout(vf_btns)

        form_var_layout.addWidget(self.var_fields_box)
        self.param_stack.addWidget(form_var_widget)

        # Page 2: script
        script_widget = QWidget()
        script_layout = QFormLayout(script_widget)
        script_layout.setContentsMargins(0, 0, 0, 0)
        self.var_script_edit = QLineEdit()
        self.var_script_edit.setPlaceholderText("e.g. /path/to/script.sh or python script.py")
        self.var_script_edit.textChanged.connect(self.on_variable_parameter_changed)
        script_layout.addRow("Script path (path):", self.var_script_edit)
        self.param_stack.addWidget(script_widget)

        # Page 3: choice
        choice_widget = QWidget()
        choice_layout = QFormLayout(choice_widget)
        choice_layout.setContentsMargins(0, 0, 0, 0)
        self.var_choice_edit = QLineEdit()
        self.var_choice_edit.setPlaceholderText("Comma-separated choices, e.g. yes, no, maybe")
        self.var_choice_edit.textChanged.connect(self.on_variable_parameter_changed)
        choice_layout.addRow("Choices (values):", self.var_choice_edit)
        self.param_stack.addWidget(choice_widget)

        # Page 4: date
        date_widget = QWidget()
        date_layout = QFormLayout(date_widget)
        date_layout.setContentsMargins(0, 0, 0, 0)
        self.var_date_edit = QLineEdit()
        self.var_date_edit.setPlaceholderText("e.g. %Y-%m-%d or %d.%m.%Y")
        self.var_date_edit.textChanged.connect(self.on_variable_parameter_changed)
        date_layout.addRow("Date format (format):", self.var_date_edit)
        self.param_stack.addWidget(date_widget)

        var_detail_layout.addWidget(self.param_stack)
        var_detail_layout.addStretch(1)

        var_scroll_area.setWidget(var_detail_panel)
        self.var_config_stack.addWidget(var_scroll_area)

        self.variables_splitter.addWidget(self.var_config_stack)
        self.variables_splitter.setStretchFactor(0, 0)
        self.variables_splitter.setStretchFactor(1, 1)
        self.variables_splitter.setSizes([200, 480])
        self.variables_splitter.setMinimumHeight(380)

        variables_layout.addWidget(self.variables_splitter)
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
