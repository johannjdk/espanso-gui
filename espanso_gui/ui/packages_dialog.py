"""Espanso Hub package browser and package manager."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config_service import ConfigService
from ..updater import parse_version


class HubFetchThread(QThread):
    loaded = Signal(list)
    failed = Signal(str)

    def __init__(self, force_refresh: bool = False, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.force_refresh = force_refresh

    def run(self) -> None:
        try:
            packages = ConfigService.fetch_hub_packages(self.force_refresh)
            self.loaded.emit(packages)
        except Exception as exc:
            self.failed.emit(str(exc))


class PackageActionThread(QThread):
    started = Signal(str)
    finished = Signal(bool, str, str)

    def __init__(
        self,
        action: str,
        name: str = "",
        version: str | None = None,
        force: bool = False,
        git: str | None = None,
        git_branch: str | None = None,
        external: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.action = action
        self.name = name
        self.version = version
        self.force = force
        self.git = git
        self.git_branch = git_branch
        self.external = external

    def run(self) -> None:
        try:
            if self.action == "install":
                res = ConfigService.install_package(self.name, version=self.version, force=self.force)
            elif self.action == "install_git":
                res = ConfigService.install_package(
                    self.name, git=self.git, git_branch=self.git_branch, external=self.external, force=self.force
                )
            elif self.action == "uninstall":
                res = ConfigService.uninstall_package(self.name)
            elif self.action == "update":
                res = ConfigService.update_package(self.name)
            elif self.action == "update_all":
                res = ConfigService.update_package("all")
            else:
                self.finished.emit(False, self.action, f"Unknown action: {self.action}")
                return

            output = (res.stdout.strip() or res.stderr.strip())
            if res.returncode == 0:
                self.finished.emit(True, self.action, output or "Operation completed successfully.")
            else:
                self.finished.emit(False, self.action, output or f"Command failed with code {res.returncode}")
        except Exception as exc:
            self.finished.emit(False, self.action, str(exc))


class InstallGitPackageDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Install package from Git")
        self.resize(460, 220)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. my-package")
        form.addRow("Package name:", self.name_edit)

        self.git_edit = QLineEdit()
        self.git_edit.setPlaceholderText("https://github.com/owner/repository")
        form.addRow("Git repository URL:", self.git_edit)

        self.branch_edit = QLineEdit()
        self.branch_edit.setPlaceholderText("Optional (e.g. main)")
        form.addRow("Git branch:", self.branch_edit)

        self.force_cb = QCheckBox("Overwrite if already installed (--force)")
        form.addRow("", self.force_cb)

        self.external_cb = QCheckBox("Allow external repository (--external)")
        self.external_cb.setChecked(True)
        self.external_cb.setToolTip("Required by Espanso when installing from non-verified git repositories.")
        form.addRow("", self.external_cb)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Install")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Please enter a package name.")
            self.name_edit.setFocus()
            return
        if not self.git_edit.text().strip():
            QMessageBox.warning(self, "Missing URL", "Please enter a Git repository URL.")
            self.git_edit.setFocus()
            return
        self.accept()

    def get_values(self) -> tuple[str, str, str | None, bool, bool]:
        branch = self.branch_edit.text().strip() or None
        return (
            self.name_edit.text().strip(),
            self.git_edit.text().strip(),
            branch,
            self.force_cb.isChecked(),
            self.external_cb.isChecked(),
        )


class PackagesDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, config_dir: Path | None = None) -> None:
        super().__init__(parent)
        self.config_dir = config_dir or ConfigService.detect_config_path()
        self.hub_packages: list[dict[str, object]] = []
        self.installed_packages: dict[str, dict[str, object]] = {}
        self.current_package: dict[str, object] | None = None
        self._action_thread: PackageActionThread | None = None
        self._fetch_thread: HubFetchThread | None = None

        self.setWindowTitle("Espanso Hub packages")
        self.resize(960, 600)

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search packages by title, name, description, tags, author…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.search_edit, 1)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All packages", "all")
        self.filter_combo.addItem("Installed", "installed")
        self.filter_combo.addItem("Available", "available")
        self.filter_combo.addItem("Update available", "updates")
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.filter_combo)

        self.git_btn = QPushButton("Install from Git…")
        self.git_btn.clicked.connect(self._open_git_install_dialog)
        toolbar.addWidget(self.git_btn)

        self.update_all_btn = QPushButton("Update all")
        self.update_all_btn.clicked.connect(self._update_all_packages)
        toolbar.addWidget(self.update_all_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(lambda: self.load_data(force_refresh=True))
        toolbar.addWidget(self.refresh_btn)

        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Package", "Latest", "Installed", "Author"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._on_package_selected)
        left_layout.addWidget(self.table)
        splitter.addWidget(left_widget)

        self.detail_panel = self._build_detail_panel()
        splitter.addWidget(self.detail_panel)
        splitter.setSizes([560, 400])

        layout.addWidget(splitter, 1)

        bottom_bar = QHBoxLayout()
        self.status_label = QLabel("Loading packages…")
        bottom_bar.addWidget(self.status_label, 1)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(self.close_btn)

        layout.addLayout(bottom_bar)

        self.load_data()

    def _build_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)

        self.title_label = QLabel("Select a package")
        title_font = self.title_label.font()
        title_font.setPointSize(title_font.pointSize() + 2)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.pkg_name_label = QLabel()
        self.pkg_name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.pkg_name_label)

        self.status_badge = QLabel()
        self.status_badge.setWordWrap(True)
        layout.addWidget(self.status_badge)

        actions_box = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_box)

        action_row = QHBoxLayout()
        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self._install_current)
        action_row.addWidget(self.install_btn)

        self.uninstall_btn = QPushButton("Uninstall")
        self.uninstall_btn.clicked.connect(self._uninstall_current)
        action_row.addWidget(self.uninstall_btn)

        self.update_btn = QPushButton("Update")
        self.update_btn.clicked.connect(self._update_current)
        action_row.addWidget(self.update_btn)

        self.open_btn = QPushButton("Open file…")
        self.open_btn.setToolTip("Open the installed package YAML in Espanso GUI")
        self.open_btn.clicked.connect(self._open_installed_file)
        action_row.addWidget(self.open_btn)
        actions_layout.addLayout(action_row)

        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel("Version:"))
        self.version_combo = QComboBox()
        opts_row.addWidget(self.version_combo, 1)

        self.force_cb = QCheckBox("Force (--force)")
        self.force_cb.setToolTip("Force reinstall or overwrite existing local files")
        opts_row.addWidget(self.force_cb)
        actions_layout.addLayout(opts_row)

        layout.addWidget(actions_box)

        meta_form = QFormLayout()
        self.author_val = QLabel()
        self.author_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        meta_form.addRow("Author:", self.author_val)

        self.tags_val = QLabel()
        self.tags_val.setWordWrap(True)
        meta_form.addRow("Tags:", self.tags_val)

        self.hub_link = QLabel()
        self.hub_link.setOpenExternalLinks(True)
        meta_form.addRow("Espanso Hub:", self.hub_link)

        self.home_link = QLabel()
        self.home_link.setOpenExternalLinks(True)
        meta_form.addRow("Homepage:", self.home_link)
        layout.addLayout(meta_form)

        layout.addWidget(QLabel("Description:"))
        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        layout.addWidget(self.desc_text, 1)

        self.triggers_label = QLabel()
        self.triggers_label.setWordWrap(True)
        self.triggers_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.triggers_label)

        self._set_detail_enabled(False)
        return panel

    def _set_detail_enabled(self, enabled: bool) -> None:
        self.install_btn.setEnabled(enabled)
        self.uninstall_btn.setEnabled(False)
        self.update_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.version_combo.setEnabled(enabled)
        self.force_cb.setEnabled(enabled)

    def load_data(self, force_refresh: bool = False) -> None:
        self.status_label.setText("Fetching Espanso Hub packages…")
        self.refresh_btn.setEnabled(False)
        self.table.setEnabled(False)

        installed_list = ConfigService.list_installed_packages(self.config_dir)
        self.installed_packages = {str(item["name"]): item for item in installed_list}

        self._fetch_thread = HubFetchThread(force_refresh=force_refresh, parent=self)
        self._fetch_thread.loaded.connect(self._on_hub_loaded)
        self._fetch_thread.failed.connect(self._on_hub_failed)
        self._fetch_thread.start()

    def _on_hub_loaded(self, packages: list[dict[str, object]]) -> None:
        self.hub_packages = packages
        self.refresh_btn.setEnabled(True)
        self.table.setEnabled(True)
        self._refresh_installed()
        self._apply_filter()

    def _on_hub_failed(self, error: str) -> None:
        self.refresh_btn.setEnabled(True)
        self.table.setEnabled(True)
        self.status_label.setText(f"Failed to fetch Hub packages: {error}")
        self._refresh_installed()
        self._apply_filter()

    def _refresh_installed(self) -> None:
        installed_list = ConfigService.list_installed_packages(self.config_dir)
        self.installed_packages = {str(item["name"]): item for item in installed_list}

    def _apply_filter(self) -> None:
        query = self.search_edit.text().strip().casefold()
        mode = self.filter_combo.currentData() or "all"

        all_names = set(p["name"] for p in self.hub_packages)
        combined_packages: list[dict[str, object]] = list(self.hub_packages)

        for name, inst in self.installed_packages.items():
            if name not in all_names:
                combined_packages.append({
                    "name": name,
                    "title": inst.get("title") or name,
                    "author": inst.get("author", ""),
                    "description": inst.get("description", ""),
                    "tags": inst.get("tags") or [],
                    "version": inst.get("version", ""),
                    "versions": [inst.get("version", "")] if inst.get("version") else [],
                    "archive_url": "",
                })

        filtered: list[dict[str, object]] = []
        for pkg in combined_packages:
            name = str(pkg["name"])
            title = str(pkg.get("title", ""))
            author = str(pkg.get("author", ""))
            desc = str(pkg.get("description", ""))
            tags = " ".join(pkg.get("tags") or [])
            search_blob = f"{name} {title} {author} {desc} {tags}".casefold()

            if query and query not in search_blob:
                continue

            is_installed = name in self.installed_packages
            installed_ver = str(self.installed_packages[name].get("version", "")) if is_installed else ""
            latest_ver = str(pkg.get("version", ""))
            has_update = is_installed and installed_ver and latest_ver and parse_version(latest_ver) > parse_version(installed_ver)

            if mode == "installed" and not is_installed:
                continue
            if mode == "available" and is_installed:
                continue
            if mode == "updates" and not has_update:
                continue

            filtered.append(pkg)

        filtered.sort(key=lambda p: str(p["name"]).casefold())

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(filtered))

        for row, pkg in enumerate(filtered):
            name = str(pkg["name"])
            title = str(pkg.get("title") or name)
            latest_ver = str(pkg.get("version") or "")
            author = str(pkg.get("author") or "")

            is_installed = name in self.installed_packages
            installed_ver = str(self.installed_packages[name].get("version", "")) if is_installed else ""
            has_update = is_installed and installed_ver and latest_ver and parse_version(latest_ver) > parse_version(installed_ver)

            if has_update:
                status_text = f"Update ({latest_ver})"
            elif is_installed:
                status_text = "Installed"
            else:
                status_text = "Available"

            item_title = QTableWidgetItem(f"{title} ({name})")
            item_title.setData(Qt.ItemDataRole.UserRole, pkg)
            item_ver = QTableWidgetItem(latest_ver)
            item_status = QTableWidgetItem(installed_ver if is_installed else status_text)
            item_author = QTableWidgetItem(author)

            self.table.setItem(row, 0, item_title)
            self.table.setItem(row, 1, item_ver)
            self.table.setItem(row, 2, item_status)
            self.table.setItem(row, 3, item_author)

        self.table.setSortingEnabled(True)

        inst_count = len(self.installed_packages)
        total_count = len(combined_packages)
        self.status_label.setText(f"Showing {len(filtered)} of {total_count} packages ({inst_count} installed)")

        if filtered:
            self.table.selectRow(0)
        else:
            self.current_package = None
            self.title_label.setText("No matching packages")
            self.pkg_name_label.setText("")
            self.status_badge.setText("")
            self.desc_text.clear()
            self._set_detail_enabled(False)

    def _on_package_selected(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        item = self.table.item(row, 0)
        if not item:
            return
        pkg = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(pkg, dict):
            return

        self.current_package = pkg
        name = str(pkg["name"])
        title = str(pkg.get("title") or name)
        author = str(pkg.get("author") or "Unknown")
        desc = str(pkg.get("description") or "No description provided.")
        tags = pkg.get("tags") or []
        latest_ver = str(pkg.get("version") or "")

        is_installed = name in self.installed_packages
        inst_info = self.installed_packages.get(name, {})
        installed_ver = str(inst_info.get("version", "")) if is_installed else ""
        has_update = is_installed and installed_ver and latest_ver and parse_version(latest_ver) > parse_version(installed_ver)

        self.title_label.setText(title)
        self.pkg_name_label.setText(f"Package ID: {name}")

        if has_update:
            self.status_badge.setText(f"Status: Installed ({installed_ver}) - Update available: {latest_ver}")
            self.status_badge.setStyleSheet("color: #d29922; font-weight: bold;")
        elif is_installed:
            self.status_badge.setText(f"Status: Installed (v{installed_ver or 'unknown'})")
            self.status_badge.setStyleSheet("color: #3fb950; font-weight: bold;")
        else:
            self.status_badge.setText(f"Status: Available on Hub (v{latest_ver})")
            self.status_badge.setStyleSheet("color: #8b949e;")

        self.author_val.setText(author)
        self.tags_val.setText(", ".join(str(t) for t in tags) if tags else "None")

        hub_url = f"https://hub.espanso.org/{name}"
        self.hub_link.setText(f'<a href="{hub_url}">{hub_url}</a>')

        homepage = str(inst_info.get("homepage") or "")
        if homepage:
            self.home_link.setText(f'<a href="{homepage}">{homepage}</a>')
        else:
            self.home_link.setText("None")

        self.desc_text.setPlainText(desc)

        self.version_combo.clear()
        versions = pkg.get("versions") or ([latest_ver] if latest_ver else [])
        for v in versions:
            self.version_combo.addItem(v, v)
        if latest_ver and self.version_combo.count() > 0:
            self.version_combo.setCurrentText(latest_ver)

        self.install_btn.setEnabled(True)
        self.install_btn.setText("Reinstall" if is_installed else "Install")
        self.uninstall_btn.setEnabled(is_installed)
        self.update_btn.setEnabled(is_installed)
        self.open_btn.setEnabled(is_installed)
        self.version_combo.setEnabled(True)
        self.force_cb.setEnabled(True)

        if is_installed and inst_info.get("path"):
            pkg_path = Path(inst_info["path"])
            triggers = self._find_package_triggers(pkg_path)
            if triggers:
                self.triggers_label.setText("Trigger preview: " + ", ".join(f'"{t}"' for t in triggers[:8]))
            else:
                self.triggers_label.setText("Trigger preview: None detected")
        else:
            self.triggers_label.setText("")

    def _find_package_triggers(self, pkg_path: Path) -> list[str]:
        triggers = []
        for yml in pkg_path.glob("*.yml"):
            if yml.name.startswith(("_", ".")):
                continue
            try:
                matches, _ = ConfigService.parse_yaml_document(yml)
                for m in matches:
                    if m.trigger:
                        triggers.append(m.trigger)
                    elif m.triggers:
                        triggers.extend(m.triggers)
            except Exception:
                pass
        return triggers

    def _install_current(self) -> None:
        if not self.current_package:
            return
        name = str(self.current_package["name"])
        version = self.version_combo.currentData() or None
        force = self.force_cb.isChecked()
        self._run_package_action("install", name=name, version=version, force=force)

    def _uninstall_current(self) -> None:
        if not self.current_package:
            return
        name = str(self.current_package["name"])
        confirm = QMessageBox.question(
            self,
            "Uninstall package",
            f'Are you sure you want to uninstall "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._run_package_action("uninstall", name=name)

    def _update_current(self) -> None:
        if not self.current_package:
            return
        name = str(self.current_package["name"])
        self._run_package_action("update", name=name)

    def _update_all_packages(self) -> None:
        if not self.installed_packages:
            QMessageBox.information(self, "No packages", "No packages are currently installed.")
            return
        self._run_package_action("update_all", name="all")

    def _open_git_install_dialog(self) -> None:
        dialog = InstallGitPackageDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, git_url, branch, force, external = dialog.get_values()
            self._run_package_action(
                "install_git", name=name, git=git_url, git_branch=branch, force=force, external=external
            )

    def _open_installed_file(self) -> None:
        if not self.current_package:
            return
        name = str(self.current_package["name"])
        inst = self.installed_packages.get(name)
        if not inst or not inst.get("path"):
            return
        pkg_path = Path(inst["path"])
        candidates = [p for p in pkg_path.glob("*.yml") if not p.name.startswith(("_", "."))]
        if not candidates:
            QMessageBox.information(self, "No match file", f'No match YAML file found in package "{name}".')
            return
        target_file = candidates[0]

        parent_win = self.parent()
        if parent_win is not None and hasattr(parent_win, "load_file"):
            self.accept()
            parent_win.load_file(target_file)
            if hasattr(parent_win, "load_files"):
                parent_win.load_files(selected_path=target_file)

    def _run_package_action(
        self,
        action: str,
        name: str = "",
        version: str | None = None,
        force: bool = False,
        git: str | None = None,
        git_branch: str | None = None,
        external: bool = False,
    ) -> None:
        self._set_buttons_enabled(False)
        self.status_label.setText(f"Running espanso package {action} {name}…")

        self._action_thread = PackageActionThread(
            action=action,
            name=name,
            version=version,
            force=force,
            git=git,
            git_branch=git_branch,
            external=external,
            parent=self,
        )
        self._action_thread.finished.connect(self._on_action_finished)
        self._action_thread.start()

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self.install_btn.setEnabled(enabled)
        self.uninstall_btn.setEnabled(enabled)
        self.update_btn.setEnabled(enabled)
        self.git_btn.setEnabled(enabled)
        self.update_all_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)

    def _on_action_finished(self, success: bool, action: str, output: str) -> None:
        self._set_buttons_enabled(True)
        self._refresh_installed()
        self._apply_filter()

        parent_win = self.parent()
        if parent_win is not None and hasattr(parent_win, "load_files"):
            parent_win.load_files()

        if success:
            self.status_label.setText(f"Completed {action}.")
            if action in ("install", "install_git"):
                reply = QMessageBox.question(
                    self,
                    "Package installed",
                    f"{output}\n\nRestart Espanso now to activate new snippets?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    ConfigService.restart_espanso()
                    if parent_win is not None and hasattr(parent_win, "update_espanso_status"):
                        parent_win.update_espanso_status()
            elif action == "uninstall":
                QMessageBox.information(self, "Package uninstalled", output)
            elif action in ("update", "update_all"):
                QMessageBox.information(self, "Packages updated", output)
        else:
            self.status_label.setText(f"Error during {action}.")
            QMessageBox.critical(self, "Package operation failed", output)
