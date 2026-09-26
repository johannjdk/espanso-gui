"""Application data models for Espanso match files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EspansoVariable:
    name: str = ""
    type: str = "shell"
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def parameter_key(self) -> str:
        """Return the primary parameter label appropriate for the variable type."""
        if self.type == "shell":
            return "cmd"
        if self.type == "script":
            return "path"
        if self.type == "form":
            return "layout"
        if self.type == "choice":
            return "choices"
        return "format"

    @property
    def parameter_value(self) -> str:
        value = self.params.get(self.parameter_key, "")
        if self.type == "choice" and isinstance(value, list):
            return ", ".join(str(item) for item in value)
        return "" if value is None else str(value)

    def set_parameter_value(self, value: str) -> None:
        if self.type == "choice":
            self.params[self.parameter_key] = [item.strip() for item in value.split(",") if item.strip()]
        else:
            self.params[self.parameter_key] = value

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> "EspansoVariable":
        return cls(
            name=str(data.get("name", "")),
            type=str(data.get("type", "shell")),
            params=dict(data.get("params") or {}),
        )

    def to_yaml(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name, "type": self.type}
        if self.params:
            data["params"] = self.params
        return data


@dataclass
class EspansoFormField:
    name: str = ""
    type: str = "text"  # "text", "choice", "list"
    multiline: bool = False
    values: list[str] = field(default_factory=list)
    default: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, name: str, data: Any) -> "EspansoFormField":
        if not isinstance(data, dict):
            return cls(name=name)
        field_type = str(data.get("type", "text")).lower()
        if field_type not in ("choice", "list"):
            field_type = "text"
        multiline = bool(data.get("multiline", False))
        raw_values = data.get("values", [])
        if isinstance(raw_values, str):
            values = [v.strip() for v in raw_values.splitlines() if v.strip()]
        elif isinstance(raw_values, list):
            values = [str(v) for v in raw_values]
        else:
            values = []
        default_val = str(data.get("default", "")) if data.get("default") is not None else ""
        known = {"type", "multiline", "values", "default"}
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(
            name=name,
            type=field_type,
            multiline=multiline,
            values=values,
            default=default_val,
            extra=extra,
        )

    def to_yaml(self) -> dict[str, Any]:
        data = dict(self.extra)
        if self.type in ("choice", "list"):
            data["type"] = self.type
            data["values"] = self.values
        else:
            if self.multiline:
                data["multiline"] = True
        if self.default:
            data["default"] = self.default
        return data


@dataclass
class EspansoMatch:
    trigger: str = ""
    replace: str = ""
    form: str = ""
    form_fields: dict[str, EspansoFormField] = field(default_factory=dict)
    mode: str = "replace"  # "replace" or "form"
    word: bool = False
    variables: list[EspansoVariable] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_form(self) -> bool:
        return self.mode == "form" or bool(self.form)

    @property
    def preview(self) -> str:
        text = self.form if self.is_form else self.replace
        preview = text.replace("\n", " ↵ ")
        if len(preview) > 80:
            preview = preview[:80] + "…"
        return preview

    def detect_field_names(self) -> list[str]:
        """Extract all unique [[field_name]] variables found in the form layout."""
        if not self.form:
            return []
        matches = re.findall(r"\[\[\s*([A-Za-z0-9_]+)\s*\]\]", self.form)
        seen = set()
        result = []
        for name in matches:
            if name not in seen:
                seen.add(name)
                result.append(name)
        return result

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> "EspansoMatch":
        has_form = "form" in data or "form_fields" in data
        mode = "form" if has_form else "replace"
        form = str(data.get("form", "")) if has_form else ""
        replace = str(data.get("replace", "")) if not has_form else ""
        raw_fields = data.get("form_fields") or {}
        form_fields: dict[str, EspansoFormField] = {}
        if isinstance(raw_fields, dict):
            for k, v in raw_fields.items():
                form_fields[str(k)] = EspansoFormField.from_yaml(str(k), v)

        known = {"trigger", "replace", "form", "form_fields", "vars", "word"}
        return cls(
            trigger=str(data.get("trigger", "")),
            replace=replace,
            form=form,
            form_fields=form_fields,
            mode=mode,
            word=bool(data.get("word", False)),
            variables=[EspansoVariable.from_yaml(v) for v in data.get("vars", []) if isinstance(v, dict)],
            extra={key: value for key, value in data.items() if key not in known},
        )

    def to_yaml(self) -> dict[str, Any]:
        data: dict[str, Any] = dict(self.extra)
        data["trigger"] = self.trigger
        data.pop("replace", None)
        data.pop("form", None)
        data.pop("form_fields", None)
        if self.is_form:
            data["form"] = self.form
            fields_dict: dict[str, Any] = {}
            for k, field_obj in self.form_fields.items():
                f_yaml = field_obj.to_yaml()
                if f_yaml:
                    fields_dict[k] = f_yaml
            if fields_dict:
                data["form_fields"] = fields_dict
        else:
            data["replace"] = self.replace

        if self.variables:
            data["vars"] = [variable.to_yaml() for variable in self.variables]
        else:
            data.pop("vars", None)
        if self.word:
            data["word"] = True
        else:
            data.pop("word", None)
        return data
