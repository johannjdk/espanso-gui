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
    def detect_var_fields(self) -> None:
        layout_text = self.variable_layout_edit.toPlainText()
        if not hasattr(self, "_current_var_fields"):
            self._current_var_fields = {}
        detected = re.findall(r"\[\[\s*([A-Za-z0-9_]+)\s*\]\]", layout_text)
        seen: set[str] = set()
        for name in detected:
            if name not in seen:
                seen.add(name)
                if name not in self._current_var_fields:
                    self._current_var_fields[name] = EspansoFormField(name=name, type="text")
        self.refresh_var_fields_table()

    def refresh_var_fields_table(self) -> None:
        self.var_fields_table.setRowCount(0)
        fields = getattr(self, "_current_var_fields", {})
        self.var_fields_table.setRowCount(len(fields))
        for row, (name, field_obj) in enumerate(fields.items()):
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
            self.var_fields_table.setItem(row, 0, QTableWidgetItem(name))
            self.var_fields_table.setItem(row, 1, QTableWidgetItem(type_desc))
            self.var_fields_table.setItem(row, 2, QTableWidgetItem(values_desc))
            self.var_fields_table.setItem(row, 3, QTableWidgetItem(field_obj.default))

    def on_var_field_selected(self) -> None:
        rows = self.var_fields_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        name_item = self.var_fields_table.item(row, 0)
        if not name_item:
            return
        name = name_item.text()
        fields = getattr(self, "_current_var_fields", {})
        field_obj = fields.get(name)
        if not field_obj:
            return
        self.selected_var_field = name
        self.var_field_name_edit.setText(field_obj.name)
        if field_obj.type == "choice":
            self.var_field_type_combo.setCurrentText("Choice Box (dropdown)")
        elif field_obj.type == "list":
            self.var_field_type_combo.setCurrentText("List Box")
        elif field_obj.multiline:
            self.var_field_type_combo.setCurrentText("Text (multiline)")
        else:
            self.var_field_type_combo.setCurrentText("Text (single-line)")
        self.var_field_values_edit.setText(", ".join(field_obj.values))
        self.var_field_default_edit.setText(field_obj.default)
        self.btn_apply_var_field.setEnabled(True)
        self.btn_delete_var_field.setEnabled(True)

    def on_var_field_type_changed(self, text: str) -> None:
        is_choice_or_list = "Choice" in text or "List" in text
        self.var_field_values_edit.setEnabled(is_choice_or_list)
        self.var_field_values_label.setEnabled(is_choice_or_list)

    def _var_field_from_inputs(self, name: str) -> EspansoFormField:
        type_text = self.var_field_type_combo.currentText()
        field_type = "text"
        multiline = False
        if "Choice" in type_text:
            field_type = "choice"
        elif "List" in type_text:
            field_type = "list"
        elif "multiline" in type_text:
            multiline = True

        raw_values = self.var_field_values_edit.text().strip()
        values = [v.strip() for v in raw_values.split(",") if v.strip()] if raw_values else []
        default_val = self.var_field_default_edit.text().strip()
        return EspansoFormField(
            name=name,
            type=field_type,
            multiline=multiline,
            values=values,
            default=default_val,
        )

    def add_var_field(self) -> None:
        name = self.var_field_name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Field name", "Please enter a field name.")
            self.var_field_name_edit.setFocus()
            return
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
            QMessageBox.warning(self, "Invalid name", "Field names may only contain letters, numbers, and underscores.")
            return
        if not hasattr(self, "_current_var_fields"):
            self._current_var_fields = {}
        field_obj = self._var_field_from_inputs(name)
        self._current_var_fields[name] = field_obj
        self.refresh_var_fields_table()
        self.clear_var_field_form()

    def update_var_field(self) -> None:
        if not getattr(self, "selected_var_field", ""):
            return
        name = self.var_field_name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Field name", "Please enter a field name.")
            return
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
            QMessageBox.warning(self, "Invalid name", "Field names may only contain letters, numbers, and underscores.")
            return
        if not hasattr(self, "_current_var_fields"):
            self._current_var_fields = {}
        if name != self.selected_var_field and self.selected_var_field in self._current_var_fields:
            del self._current_var_fields[self.selected_var_field]
        field_obj = self._var_field_from_inputs(name)
        self._current_var_fields[name] = field_obj
        self.selected_var_field = name
        self.refresh_var_fields_table()

    def delete_var_field(self) -> None:
        if not getattr(self, "selected_var_field", ""):
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
        if hasattr(self, "_current_var_fields") and self.selected_var_field in self._current_var_fields:
            del self._current_var_fields[self.selected_var_field]
            self.refresh_var_fields_table()
            self.clear_var_field_form()

    def clear_var_field_form(self) -> None:
        self.selected_var_field = ""
        self.var_field_name_edit.clear()
        self.var_field_type_combo.setCurrentIndex(0)
        self.var_field_values_edit.clear()
        self.var_field_default_edit.clear()
        self.var_field_values_edit.setEnabled(False)
        self.var_field_values_label.setEnabled(False)
        self.btn_apply_var_field.setEnabled(False)
        self.btn_delete_var_field.setEnabled(False)

    def refresh_variable_table(self) -> None:
        self.variable_table.setRowCount(0)
        if not (0 <= self.selected_match < len(self.matches)):
            return
        variables = self.matches[self.selected_match].variables
        self.variable_table.setRowCount(len(variables))
        for row, variable in enumerate(variables):
            self.variable_table.setItem(row, 0, QTableWidgetItem(variable.name))
            self.variable_table.setItem(row, 1, QTableWidgetItem(variable.type))
            param_val = variable.parameter_value
            display = param_val.replace("\n", " ↵ ") if "\n" in param_val else param_val
            item = QTableWidgetItem(display)
            tooltip = param_val
            if variable.type == "form" and variable.fields:
                field_lines = []
                for fname, fobj in variable.fields.items():
                    desc = fobj.type
                    if fobj.type in ("choice", "list") and fobj.values:
                        desc += f" [{', '.join(fobj.values)}]"
                    elif fobj.multiline:
                        desc = "multiline text"
                    if fobj.default:
                        desc += f" (default: {fobj.default})"
                    field_lines.append(f"  • {fname}: {desc}")
                tooltip = f"{param_val}\n\nFields:\n" + "\n".join(field_lines)
            item.setToolTip(tooltip)
            self.variable_table.setItem(row, 2, item)

    def clear_variable_form(self) -> None:
        self.selected_variable = -1
        self.variable_name.clear()
        self.variable_parameter.clear()
        self.variable_layout_edit.clear()
        self.variable_type.setCurrentText("shell")
        self.parameter_stack.setCurrentIndex(0)
        self._current_var_fields = {}
        self.refresh_var_fields_table()
        self.clear_var_field_form()
        if hasattr(self, "var_fields_box"):
            self.var_fields_box.hide()
        self.update_variable_button.setEnabled(False)

    def update_parameter_label(self, variable_type: str) -> None:
        labels = {
            "shell": "cmd:",
            "script": "path:",
            "date": "format:",
            "form": "layout:",
            "choice": "choices:",
        }
        self.parameter_label.setText(labels.get(variable_type, "param:"))
        self.variable_parameter.setPlaceholderText(
            "Comma-separated choices, e.g. yes, no" if variable_type == "choice" else ""
        )
        if variable_type == "form":
            self.parameter_stack.setCurrentIndex(1)
            if hasattr(self, "var_fields_box"):
                self.var_fields_box.show()
        else:
            self.parameter_stack.setCurrentIndex(0)
            if hasattr(self, "var_fields_box"):
                self.var_fields_box.hide()

    def _variable_from_form(self, existing: EspansoVariable | None = None) -> EspansoVariable | None:
        name = self.variable_name.text().strip()
        if not name:
            QMessageBox.information(self, "Variable name", "Please enter a variable name.")
            self.variable_name.setFocus()
            return None
        variable = existing or EspansoVariable()
        variable.name = name
        variable.type = self.variable_type.currentText()
        if variable.type == "form":
            variable.set_parameter_value(self.variable_layout_edit.toPlainText())
            variable.fields = {
                k: EspansoFormField(
                    name=v.name,
                    type=v.type,
                    multiline=v.multiline,
                    values=list(v.values),
                    default=v.default,
                    extra=dict(v.extra),
                )
                for k, v in getattr(self, "_current_var_fields", {}).items()
            }
        else:
            variable.set_parameter_value(self.variable_parameter.text())
            variable.fields = {}
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
        if variable.type == "form":
            self.variable_layout_edit.setPlainText(variable.parameter_value)
            self.variable_parameter.clear()
            self._current_var_fields = {
                k: EspansoFormField(
                    name=v.name,
                    type=v.type,
                    multiline=v.multiline,
                    values=list(v.values),
                    default=v.default,
                    extra=dict(v.extra),
                )
                for k, v in variable.fields.items()
            }
            self.refresh_var_fields_table()
            self.clear_var_field_form()
            if hasattr(self, "var_fields_box"):
                self.var_fields_box.show()
        else:
            self.variable_parameter.setText(variable.parameter_value)
            self.variable_layout_edit.clear()
            self._current_var_fields = {}
            self.refresh_var_fields_table()
            self.clear_var_field_form()
            if hasattr(self, "var_fields_box"):
                self.var_fields_box.hide()
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
