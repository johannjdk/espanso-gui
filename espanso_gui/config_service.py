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
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)



def _str_presenter(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


EspansoYamlDumper.add_representer(str, _str_presenter)


class ConfigService:
    @staticmethod
    def match_files(directory: Path) -> list[Path]:
        return sorted(
            (
                path for path in directory.rglob("*")
                if path.is_file()
                and path.suffix in (".yml", ".yaml")
                and not path.name.startswith(("_", "."))
            ),
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
    def get_show_line_numbers() -> bool:
        val = QSettings("EspansoGUI", "EspansoGUI").value("show_line_numbers", True)
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            return val.lower() not in ("false", "0", "no")
        return True

    @staticmethod
    def set_show_line_numbers(enabled: bool) -> None:
        QSettings("EspansoGUI", "EspansoGUI").setValue("show_line_numbers", bool(enabled))

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
    def format_yaml_text(text: str) -> str:
        document = yaml.safe_load(text)
        if document is None:
            return text
        return yaml.dump(
            document,
            Dumper=EspansoYamlDumper,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )

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
    def start_espanso() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["espanso", "start"], text=True, capture_output=True, check=False, timeout=20
        )

    @staticmethod
    def stop_espanso() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["espanso", "stop"], text=True, capture_output=True, check=False, timeout=20
        )

    @staticmethod
    def get_espanso_status() -> tuple[bool | None, str]:
        """Return (is_running, status_message).

        is_running is True if running, False if stopped, None if not installed / error.
        """
        try:
            res = subprocess.run(
                ["espanso", "status"], text=True, capture_output=True, check=False, timeout=5
            )
            output = (res.stdout.strip() or res.stderr.strip()).lower()
            if res.returncode == 0 or "is running" in output:
                return True, "Running"
            if "not running" in output or "stopped" in output or res.returncode != 0:
                return False, "Stopped"
            return False, "Stopped"
        except (OSError, subprocess.SubprocessError):
            return None, "Not found"

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

    @staticmethod
    def detect_packages_path() -> Path:
        """Return the directory containing installed Espanso packages."""
        return ConfigService.detect_config_path() / "packages"

    @staticmethod
    def list_installed_packages(config_dir: Path | None = None) -> list[dict[str, object]]:
        base = config_dir or ConfigService.detect_config_path()
        packages_dir = base / "packages"
        installed: list[dict[str, object]] = []
        if not packages_dir.is_dir():
            return installed

        for pkg_dir in sorted(packages_dir.iterdir(), key=lambda p: p.name.casefold()):
            if not pkg_dir.is_dir():
                continue
            manifest_file = pkg_dir / "_manifest.yml"
            manifest: dict[str, object] = {}
            if manifest_file.is_file():
                try:
                    with manifest_file.open("r", encoding="utf-8") as stream:
                        doc = yaml.safe_load(stream)
                        if isinstance(doc, dict):
                            manifest = doc
                except Exception:
                    pass

            source_file = pkg_dir / "_pkgsource.yml"
            source = ""
            if source_file.is_file():
                try:
                    source = source_file.read_text(encoding="utf-8").strip()
                except Exception:
                    pass

            name = str(manifest.get("name") or pkg_dir.name)
            title = str(manifest.get("title") or name)
            version = str(manifest.get("version") or "")
            author = str(manifest.get("author") or "")
            description = str(manifest.get("description") or "")
            homepage = str(manifest.get("homepage") or "")
            tags = manifest.get("tags") or []
            if not isinstance(tags, list):
                tags = []

            installed.append({
                "name": name,
                "title": title,
                "version": version,
                "author": author,
                "description": description,
                "homepage": homepage,
                "tags": [str(t) for t in tags],
                "source": source,
                "path": pkg_dir,
            })
        return installed

    @staticmethod
    def install_package(
        name: str,
        version: str | None = None,
        force: bool = False,
        git: str | None = None,
        git_branch: str | None = None,
        external: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        cmd = ["espanso", "package", "install"]
        if force:
            cmd.append("--force")
        if version:
            cmd.extend(["--version", version])
        if git:
            cmd.extend(["--git", git])
            if git_branch:
                cmd.extend(["--git-branch", git_branch])
        if external or git:
            cmd.append("--external")
        cmd.append(name)
        return subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=60)

    @staticmethod
    def uninstall_package(name: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["espanso", "package", "uninstall", name],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )

    @staticmethod
    def update_package(name: str = "all") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["espanso", "package", "update", name],
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )

    @staticmethod
    def fetch_hub_packages(force_refresh: bool = False) -> list[dict[str, object]]:
        import json
        import time
        import urllib.request
        from .updater import get_ssl_context, parse_version

        if sys.platform.startswith("win"):
            cache_base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        elif sys.platform == "darwin":
            cache_base = Path.home() / "Library" / "Caches"
        else:
            cache_base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        cache_file = cache_base / "espanso-gui" / "hub_packages.json"

        now = time.time()
        if not force_refresh and cache_file.is_file():
            try:
                if now - cache_file.stat().st_mtime < 3600:
                    cached = json.loads(cache_file.read_text(encoding="utf-8"))
                    if isinstance(cached, list) and cached:
                        return cached
            except Exception:
                pass

        url = "https://github.com/espanso/hub/releases/latest/download/package_index.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Espanso-GUI"})
        with urllib.request.urlopen(req, timeout=10, context=get_ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        grouped: dict[str, dict[str, object]] = {}
        for item in data.get("packages", []):
            name = item.get("name")
            if not name:
                continue
            ver = item.get("version", "")
            if name not in grouped:
                grouped[name] = {
                    "name": name,
                    "title": item.get("title") or name,
                    "author": item.get("author", ""),
                    "description": item.get("description", ""),
                    "tags": list(item.get("tags") or []),
                    "version": ver,
                    "versions": [ver] if ver else [],
                    "archive_url": item.get("archive_url", ""),
                }
            else:
                entry = grouped[name]
                versions = entry["versions"]
                if ver and ver not in versions:
                    versions.append(ver)
                if parse_version(ver) > parse_version(str(entry.get("version", ""))):
                    entry["version"] = ver
                    entry["title"] = item.get("title") or entry["title"]
                    entry["author"] = item.get("author") or entry["author"]
                    entry["description"] = item.get("description") or entry["description"]
                    if item.get("tags"):
                        entry["tags"] = sorted(set(entry["tags"] + item["tags"]))
                    if item.get("archive_url"):
                        entry["archive_url"] = item["archive_url"]

        for entry in grouped.values():
            entry["versions"].sort(key=parse_version, reverse=True)

        package_list = sorted(grouped.values(), key=lambda p: str(p["name"]).casefold())
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(package_list), encoding="utf-8")
        except OSError:
            pass

        return package_list

