"""MatchDetailsMixin."""

from __future__ import annotations

import re

from PySide6.QtWidgets import QMessageBox, QTableWidgetItem

from ..models import EspansoFormField, EspansoVariable


class MatchDetailsMixin:
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

    def on_form_field_cell_clicked(self, row: int, column: int) -> None:
        self.form_fields_table.selectRow(row)
        self.on_form_field_selected()

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
        self.form_fields_table.clearSelection()
        self.form_fields_table.setCurrentItem(None)
        self.field_name_edit.clear()
        self.field_type_combo.setCurrentIndex(0)
        self.field_values_edit.clear()
        self.field_default_edit.clear()
        self.field_values_edit.setEnabled(False)
        self.field_values_label.setEnabled(False)
        self.btn_apply_field.setEnabled(False)
        self.btn_delete_field.setEnabled(False)
    def _current_form_variable(self) -> EspansoVariable | None:
        if not (0 <= self.selected_match < len(self.matches)):
            return None
        match = self.matches[self.selected_match]
        if not (0 <= self.selected_variable < len(match.variables)):
            return None
        var = match.variables[self.selected_variable]
        if var.type != "form":
            return None
        return var

    def detect_var_fields(self) -> None:
        var = self._current_form_variable()
        if not var:
            return
        layout_text = self.variable_layout_edit.toPlainText()
        detected = re.findall(r"\[\[\s*([A-Za-z0-9_]+)\s*\]\]", layout_text)
        seen: set[str] = set()
        added = False
        for name in detected:
            if name not in seen:
                seen.add(name)
                if name not in var.fields:
                    var.fields[name] = EspansoFormField(name=name, type="text")
                    added = True
        if added:
            self.dirty = True
        self.refresh_var_fields_table()

    def refresh_var_fields_table(self) -> None:
        self._loading_var_field = True
        self.var_fields_table.setRowCount(0)
        var = self._current_form_variable()
        if not var:
            self._loading_var_field = False
            self._clear_var_field_inputs()
            return

        fields = list(var.fields.values())
        self.var_fields_table.setRowCount(len(fields))
        selected_row = -1
        for row, fobj in enumerate(fields):
            if fobj.type == "choice":
                type_desc = "Choice Box"
            elif fobj.type == "list":
                type_desc = "List Box"
            elif fobj.multiline:
                type_desc = "Text (multiline)"
            else:
                type_desc = "Text (single-line)"
            values_desc = ", ".join(fobj.values) if fobj.values else ""
            self.var_fields_table.setItem(row, 0, QTableWidgetItem(fobj.name))
            self.var_fields_table.setItem(row, 1, QTableWidgetItem(type_desc))
            self.var_fields_table.setItem(row, 2, QTableWidgetItem(values_desc))
            self.var_fields_table.setItem(row, 3, QTableWidgetItem(fobj.default))
            if getattr(self, "selected_var_field", "") == fobj.name:
                selected_row = row

        if selected_row >= 0:
            self.var_fields_table.selectRow(selected_row)
        elif fields:
            self.var_fields_table.selectRow(0)
        else:
            self._clear_var_field_inputs()
        self._loading_var_field = False

        if self.var_fields_table.currentRow() >= 0:
            self.on_var_field_selected()

    def on_var_field_selected(self) -> None:
        rows = self.var_fields_table.selectionModel().selectedRows()
        if not rows:
            self._clear_var_field_inputs()
            return
        row = rows[0].row()
        name_item = self.var_fields_table.item(row, 0)
        if not name_item:
            return
        name = name_item.text()
        var = self._current_form_variable()
        if not var or name not in var.fields:
            return
        self.selected_var_field = name
        fobj = var.fields[name]

        self._loading_var_field = True
        self.var_field_form_widget.setEnabled(True)
        self.var_field_name_edit.setText(fobj.name)
        if fobj.type == "choice":
            self.var_field_type_combo.setCurrentText("Choice Box (dropdown)")
        elif fobj.type == "list":
            self.var_field_type_combo.setCurrentText("List Box")
        elif fobj.multiline:
            self.var_field_type_combo.setCurrentText("Text (multiline)")
        else:
            self.var_field_type_combo.setCurrentText("Text (single-line)")
        self.var_field_values_edit.setText(", ".join(fobj.values))
        self.var_field_default_edit.setText(fobj.default)

        is_choice_or_list = fobj.type in ("choice", "list")
        self.var_field_values_edit.setEnabled(is_choice_or_list)
        self.var_field_values_label.setEnabled(is_choice_or_list)
        self.btn_delete_var_field.setEnabled(True)
        self._loading_var_field = False

    def on_var_field_cell_clicked(self, row: int, column: int) -> None:
        if getattr(self, "_loading_var_field", False):
            return
        self.var_fields_table.selectRow(row)
        self.on_var_field_selected()

    def on_var_field_name_editing_finished(self) -> None:
        if getattr(self, "_loading_var_field", False):
            return
        var = self._current_form_variable()
        if not var or not getattr(self, "selected_var_field", ""):
            return
        new_name = self.var_field_name_edit.text().strip()
        old_name = self.selected_var_field
        if not new_name or new_name == old_name:
            self.var_field_name_edit.setText(old_name)
            return
        if not re.fullmatch(r"[A-Za-z0-9_]+", new_name):
            QMessageBox.warning(self, "Invalid name", "Field names may only contain letters, numbers, and underscores.")
            self.var_field_name_edit.setText(old_name)
            return
        if new_name in var.fields:
            QMessageBox.warning(self, "Duplicate name", f"A field named '{new_name}' already exists.")
            self.var_field_name_edit.setText(old_name)
            return
        rebuilt = {}
        for k, v in var.fields.items():
            if k == old_name:
                v.name = new_name
                rebuilt[new_name] = v
            else:
                rebuilt[k] = v
        var.fields = rebuilt
        self.selected_var_field = new_name
        row = self.var_fields_table.currentRow()
        if row >= 0:
            item = self.var_fields_table.item(row, 0)
            if item:
                item.setText(new_name)
        self.dirty = True

    def on_var_field_type_changed(self, text: str) -> None:
        is_choice_or_list = "Choice" in text or "List" in text
        self.var_field_values_edit.setEnabled(is_choice_or_list)
        self.var_field_values_label.setEnabled(is_choice_or_list)
        if getattr(self, "_loading_var_field", False):
            return
        self._sync_current_var_field_from_inputs()

    def on_var_field_input_changed(self) -> None:
        if getattr(self, "_loading_var_field", False):
            return
        self._sync_current_var_field_from_inputs()

    def _sync_current_var_field_from_inputs(self) -> None:
        var = self._current_form_variable()
        if not var or not getattr(self, "selected_var_field", ""):
            return
        fobj = var.fields.get(self.selected_var_field)
        if not fobj:
            return
        type_text = self.var_field_type_combo.currentText()
        if "Choice" in type_text:
            fobj.type = "choice"
            fobj.multiline = False
        elif "List" in type_text:
            fobj.type = "list"
            fobj.multiline = False
        elif "multiline" in type_text:
            fobj.type = "text"
            fobj.multiline = True
        else:
            fobj.type = "text"
            fobj.multiline = False

        raw_values = self.var_field_values_edit.text().strip()
        fobj.values = [v.strip() for v in raw_values.split(",") if v.strip()] if raw_values else []
        fobj.default = self.var_field_default_edit.text()

        row = self.var_fields_table.currentRow()
        if row >= 0:
            if fobj.type == "choice":
                type_desc = "Choice Box"
            elif fobj.type == "list":
                type_desc = "List Box"
            elif fobj.multiline:
                type_desc = "Text (multiline)"
            else:
                type_desc = "Text (single-line)"
            self.var_fields_table.item(row, 1).setText(type_desc)
            self.var_fields_table.item(row, 2).setText(", ".join(fobj.values) if fobj.values else "")
            self.var_fields_table.item(row, 3).setText(fobj.default)
        self.dirty = True

    def add_var_field(self) -> None:
        var = self._current_form_variable()
        if not var:
            return
        num = 1
        while f"field{num}" in var.fields:
            num += 1
        name = f"field{num}"
        var.fields[name] = EspansoFormField(name=name, type="text")
        self.selected_var_field = name
        self.dirty = True
        self.refresh_var_fields_table()
        self.var_field_name_edit.setFocus()
        self.var_field_name_edit.selectAll()

    def delete_var_field(self) -> None:
        var = self._current_form_variable()
        if not var or not getattr(self, "selected_var_field", ""):
            return
        if (
            QMessageBox.question(
                self,
                "Delete field",
                f"Really delete field '{self.selected_var_field}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self.selected_var_field in var.fields:
            del var.fields[self.selected_var_field]
            self.selected_var_field = ""
            self.dirty = True
            self.refresh_var_fields_table()

    def _clear_var_field_inputs(self) -> None:
        self.selected_var_field = ""
        self.var_fields_table.clearSelection()
        self.var_fields_table.setCurrentItem(None)
        self.var_field_form_widget.setEnabled(False)
        self._loading_var_field = True
        self.var_field_name_edit.clear()
        self.var_field_type_combo.setCurrentIndex(0)
        self.var_field_values_edit.clear()
        self.var_field_default_edit.clear()
        self.var_field_values_edit.setEnabled(False)
        self.var_field_values_label.setEnabled(False)
        self.btn_delete_var_field.setEnabled(False)
        self._loading_var_field = False

    def clear_var_field_form(self) -> None:
        self._clear_var_field_inputs()

    def update_var_field(self) -> None:
        self._sync_current_var_field_from_inputs()

    def refresh_variable_table(self) -> None:
        self._loading_var = True
        self.variable_table.setRowCount(0)
        if not (0 <= self.selected_match < len(self.matches)):
            self.clear_variable_form()
            return
        variables = self.matches[self.selected_match].variables
        self.variable_table.setRowCount(len(variables))
        for row, variable in enumerate(variables):
            self.variable_table.setItem(row, 0, QTableWidgetItem(variable.name))
            self.variable_table.setItem(row, 1, QTableWidgetItem(variable.type))

        if variables:
            target_row = self.selected_variable if 0 <= self.selected_variable < len(variables) else 0
            self.selected_variable = target_row
            self.variable_table.selectRow(target_row)
            self.btn_delete_variable.setEnabled(True)
            self.var_config_stack.setCurrentIndex(1)
            self._loading_var = False
            self.on_variable_selected()
        else:
            self.clear_variable_form()

    def clear_variable_form(self) -> None:
        self.selected_variable = -1
        self._loading_var = True
        self.variable_table.clearSelection()
        self.variable_table.setCurrentItem(None)
        self.variable_name.clear()
        self.variable_type.setCurrentIndex(0)
        self.var_shell_edit.clear()
        self.var_script_edit.clear()
        self.var_date_edit.clear()
        self.var_choice_edit.clear()
        self.variable_layout_edit.clear()
        self.param_stack.setCurrentIndex(0)
        self.var_config_stack.setCurrentIndex(0)
        self.btn_delete_variable.setEnabled(False)
        self._clear_var_field_inputs()
        self.var_fields_table.setRowCount(0)
        self._loading_var = False

    def on_variable_cell_clicked(self, row: int, column: int) -> None:
        if getattr(self, "_loading_var", False):
            return
        self.selected_variable = row
        self.variable_table.selectRow(row)
        self.on_variable_selected()

    def on_variable_selected(self) -> None:
        if getattr(self, "_loading_var", False):
            return
        rows = self.variable_table.selectionModel().selectedRows()
        if not rows or not (0 <= self.selected_match < len(self.matches)):
            self.selected_variable = -1
            self.var_config_stack.setCurrentIndex(0)
            self.btn_delete_variable.setEnabled(False)
            return
        self.selected_variable = rows[0].row()
        match = self.matches[self.selected_match]
        if not (0 <= self.selected_variable < len(match.variables)):
            return
        variable = match.variables[self.selected_variable]

        self._loading_var = True
        self.var_config_stack.setCurrentIndex(1)
        self.btn_delete_variable.setEnabled(True)
        self.variable_name.setText(variable.name)
        self.variable_type.setCurrentText(variable.type)

        type_to_index = {
            "shell": 0,
            "form": 1,
            "script": 2,
            "choice": 3,
            "date": 4,
        }
        self.param_stack.setCurrentIndex(type_to_index.get(variable.type, 0))
        self._load_variable_param_inputs(variable)
        self._loading_var = False

    def _load_variable_param_inputs(self, variable: EspansoVariable) -> None:
        val = variable.parameter_value
        if variable.type == "shell":
            self.var_shell_edit.setText(val)
        elif variable.type == "form":
            self.variable_layout_edit.setPlainText(val)
            self.refresh_var_fields_table()
        elif variable.type == "script":
            self.var_script_edit.setText(val)
        elif variable.type == "choice":
            self.var_choice_edit.setText(val)
        elif variable.type == "date":
            self.var_date_edit.setText(val)

    def on_variable_name_changed(self, text: str) -> None:
        if getattr(self, "_loading_var", False):
            return
        if not (0 <= self.selected_match < len(self.matches)):
            return
        match = self.matches[self.selected_match]
        if not (0 <= self.selected_variable < len(match.variables)):
            return
        var = match.variables[self.selected_variable]
        var.name = text
        item = self.variable_table.item(self.selected_variable, 0)
        if item:
            item.setText(text)
        self.dirty = True

    def on_variable_type_changed(self, new_type: str) -> None:
        if getattr(self, "_loading_var", False):
            return
        if not (0 <= self.selected_match < len(self.matches)):
            return
        match = self.matches[self.selected_match]
        if not (0 <= self.selected_variable < len(match.variables)):
            return
        var = match.variables[self.selected_variable]
        var.type = new_type
        item = self.variable_table.item(self.selected_variable, 1)
        if item:
            item.setText(new_type)

        type_to_index = {
            "shell": 0,
            "form": 1,
            "script": 2,
            "choice": 3,
            "date": 4,
        }
        self.param_stack.setCurrentIndex(type_to_index.get(new_type, 0))
        self._load_variable_param_inputs(var)
        self.dirty = True

    def on_variable_parameter_changed(self) -> None:
        if getattr(self, "_loading_var", False):
            return
        if not (0 <= self.selected_match < len(self.matches)):
            return
        match = self.matches[self.selected_match]
        if not (0 <= self.selected_variable < len(match.variables)):
            return
        var = match.variables[self.selected_variable]
        if var.type == "shell":
            var.set_parameter_value(self.var_shell_edit.text())
        elif var.type == "script":
            var.set_parameter_value(self.var_script_edit.text())
        elif var.type == "choice":
            var.set_parameter_value(self.var_choice_edit.text())
        elif var.type == "date":
            var.set_parameter_value(self.var_date_edit.text())
        self.dirty = True

    def on_variable_layout_changed(self) -> None:
        if getattr(self, "_loading_var", False):
            return
        if not (0 <= self.selected_match < len(self.matches)):
            return
        match = self.matches[self.selected_match]
        if not (0 <= self.selected_variable < len(match.variables)):
            return
        var = match.variables[self.selected_variable]
        if var.type == "form":
            var.set_parameter_value(self.variable_layout_edit.toPlainText())
            self.dirty = True

    def add_variable(self) -> None:
        if not (0 <= self.selected_match < len(self.matches)):
            return
        match = self.matches[self.selected_match]
        existing_names = {v.name for v in match.variables}
        num = 1
        while f"var{num}" in existing_names:
            num += 1
        new_name = f"var{num}"
        var = EspansoVariable(name=new_name, type="shell")
        var.set_parameter_value("")
        match.variables.append(var)
        self.dirty = True
        self.selected_variable = len(match.variables) - 1
        self.refresh_variable_table()
        self.variable_name.setFocus()
        self.variable_name.selectAll()

    def delete_variable(self) -> None:
        if not (0 <= self.selected_match < len(self.matches)):
            return
        match = self.matches[self.selected_match]
        if not (0 <= self.selected_variable < len(match.variables)):
            return
        var = match.variables[self.selected_variable]
        if (
            QMessageBox.question(
                self,
                "Delete variable",
                f"Really delete variable '{var.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        del match.variables[self.selected_variable]
        self.dirty = True
        if self.selected_variable >= len(match.variables):
            self.selected_variable = len(match.variables) - 1
        self.refresh_variable_table()

    def update_variable(self) -> None:
        self.dirty = True

    def update_parameter_label(self, variable_type: str) -> None:
        pass
