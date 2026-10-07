"""Reading, writing, and locating Espanso configuration files."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

from PySide6.QtCore import QSettings

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
    def match_files(directory: Path) -> list[Path]:
        return sorted(
            (path for path in directory.rglob("*") if path.is_file() and path.suffix in (".yml", ".yaml")),
            key=lambda path: path.relative_to(directory).as_posix().casefold(),
        )

    @staticmethod
    def get_custom_espanso_path() -> Path | None:
        val = QSettings("EspansoGUI", "EspansoGUI").value("espanso_path")
        return Path(val) if val else None

    @staticmethod
    def set_custom_espanso_path(path: Path | None) -> None:
        settings = QSettings("EspansoGUI", "EspansoGUI")
        if path:
            settings.setValue("espanso_path", str(path))
        else:
            settings.remove("espanso_path")

    @staticmethod
    def get_check_updates() -> bool:
        val = QSettings("EspansoGUI", "EspansoGUI").value("check_updates", True)
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            return val.lower() not in ("false", "0", "no")
        return True

    @staticmethod
    def set_check_updates(enabled: bool) -> None:
        QSettings("EspansoGUI", "EspansoGUI").setValue("check_updates", bool(enabled))

    @staticmethod
    def get_ignored_update_version() -> str:
        return str(QSettings("EspansoGUI", "EspansoGUI").value("ignored_update_version", ""))

    @staticmethod
    def set_ignored_update_version(version: str) -> None:
        QSettings("EspansoGUI", "EspansoGUI").setValue("ignored_update_version", version)

    @staticmethod
    def default_espanso_path() -> Path:
        if sys.platform.startswith("win"):
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            return base / "espanso"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "espanso"
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / "espanso"

    @staticmethod
    def detect_espanso_path() -> Path:
        """Return Espanso's configuration root directory."""
        custom = ConfigService.get_custom_espanso_path()
        if custom and custom.is_dir():
            return custom
        return ConfigService.default_espanso_path()

    @staticmethod
    def detect_config_path() -> Path:
        """Return Espanso's match-file directory."""
        espanso_dir = ConfigService.detect_espanso_path()
        if espanso_dir.name == "match":
            return espanso_dir
        if espanso_dir.is_dir() and not (espanso_dir / "match").is_dir() and any(espanso_dir.glob("*.yml")):
            return espanso_dir
        return espanso_dir / "match"

    @staticmethod
    def detect_options_path() -> Path:
        """Return the directory containing Espanso configuration profiles."""
        espanso_dir = ConfigService.detect_espanso_path()
        if espanso_dir.name == "match":
            return espanso_dir.parent / "config"
        return espanso_dir / "config"

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

    @staticmethod
    def detect_espanso_version() -> str | None:
        try:
            res = subprocess.run(["espanso", "--version"], text=True, capture_output=True, check=False, timeout=5)
            if res.returncode == 0:
                m = re.search(r"(\d+\.\d+\.\d+)", res.stdout.strip())
                return m.group(1) if m else res.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        return None

    @staticmethod
    def is_stats_supported() -> bool:
        ver = ConfigService.detect_espanso_version()
        if not ver:
            return False
        parts = re.findall(r"\d+", ver)
        return tuple(int(p) for p in parts[:3]) >= (2, 4, 0)

    @staticmethod
    def is_stats_enabled(config_dir: Path | None = None) -> bool:
        options_dir = config_dir or ConfigService.detect_options_path()
        if options_dir.name == "match":
            candidate = options_dir.parent / "config"
            if candidate.is_dir():
                options_dir = candidate
        path = options_dir / "default.yml"
        if not path.is_file():
            return False
        try:
            with path.open("r", encoding="utf-8") as stream:
                doc = yaml.safe_load(stream) or {}
            stats = doc.get("stats")
            if isinstance(stats, dict):
                return bool(stats.get("enabled", False))
            if isinstance(stats, bool):
                return stats
        except Exception:
            pass
        return False

    @staticmethod
    def get_stats(period: str = "all", count: int = 50, grep: str | None = None) -> dict:
        import json
        cmd = ["espanso", "stats", "--json", "--period", period, "--count", str(count)]
        if grep:
            cmd.extend(["--grep", grep])
        res = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=10)
        if res.returncode == 0:
            return json.loads(res.stdout)
        raise RuntimeError(res.stderr.strip() or f"Command failed with exit code {res.returncode}")

    @staticmethod
    def clear_stats() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["espanso", "stats", "clear"], text=True, capture_output=True, check=False, timeout=10
        )

