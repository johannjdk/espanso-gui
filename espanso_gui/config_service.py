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
    def detect_espanso_path() -> Path:
        """Return Espanso's configuration root directory."""
        if sys.platform.startswith("win"):
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            return base / "espanso"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "espanso"
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / "espanso"

    @staticmethod
    def detect_config_path() -> Path:
        """Return Espanso's match-file directory."""
        return ConfigService.detect_espanso_path() / "match"

    @staticmethod
    def detect_options_path() -> Path:
        """Return the directory containing Espanso configuration profiles."""
        return ConfigService.detect_espanso_path() / "config"

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
    def validate_config_yaml(text: str) -> None:
        """Ensure an Espanso configuration profile has a YAML mapping at its root."""
        document = yaml.safe_load(text) or {}
        if not isinstance(document, dict):
            raise ValueError("The YAML root must be a mapping.")

    @staticmethod
    def save_raw_yaml(path: Path, text: str) -> None:
        ConfigService.validate_yaml_text(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")

    @staticmethod
    def save_config_yaml(path: Path, text: str) -> None:
        ConfigService.validate_config_yaml(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")

    @staticmethod
    def restart_espanso() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["espanso", "restart"], text=True, capture_output=True, check=False, timeout=20
        )
