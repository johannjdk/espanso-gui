"""Reading, writing, and locating Espanso configuration files."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

from .models import EspansoMatch


class EspansoYamlDumper(yaml.SafeDumper):
    pass


def _str_presenter(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


EspansoYamlDumper.add_representer(str, _str_presenter)


class ConfigService:
    @staticmethod
    def detect_config_path() -> Path:
        if sys.platform.startswith("win"):
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            return base / "espanso" / "match"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "espanso" / "match"
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / "espanso" / "match"

    @staticmethod
    def parse_yaml(path: Path) -> list[EspansoMatch]:
        return ConfigService.parse_yaml_document(path)[0]

    @staticmethod
    def parse_yaml_document(path: Path) -> tuple[list[EspansoMatch], dict[str, object]]:
        with path.open("r", encoding="utf-8") as stream:
            document = yaml.safe_load(stream) or {}
        if not isinstance(document, dict):
            raise ValueError("The YAML root must be a mapping.")
        extras = {key: value for key, value in document.items() if key != "matches"}
        matches = document.get("matches", [])
        if matches is None:
            return [], extras
        if not isinstance(matches, list):
            raise ValueError("'matches' must be a list.")
        return [EspansoMatch.from_yaml(item) for item in matches if isinstance(item, dict)], extras

    @staticmethod
    def save_yaml(
        path: Path, matches: list[EspansoMatch], document_extra: dict[str, object] | None = None
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        document = dict(document_extra or {})
        document["matches"] = [match.to_yaml() for match in matches]
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            yaml.dump(
                document,
                stream,
                Dumper=EspansoYamlDumper,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )

    @staticmethod
    def validate_yaml_text(text: str) -> None:
        document = yaml.safe_load(text) or {}
        if not isinstance(document, dict):
            raise ValueError("The YAML root must be a mapping.")
        matches = document.get("matches", [])
        if matches is not None and not isinstance(matches, list):
            raise ValueError("'matches' must be a list.")

    @staticmethod
    def save_raw_yaml(path: Path, text: str) -> None:
        ConfigService.validate_yaml_text(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")

    @staticmethod
    def restart_espanso() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["espanso", "restart"], text=True, capture_output=True, check=False, timeout=20
        )
