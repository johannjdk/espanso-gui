# Espanso GUI

A native desktop editor for [Espanso](https://espanso.org/) match files. Espanso
GUI makes it easier to create, review, and maintain text-expansion rules without
editing YAML by hand, while keeping your existing Espanso configuration in
control.

> Espanso GUI is an independent project and is not affiliated with Espanso.

![Espanso GUI](images/demo.png)

## Features

- Browse, create, duplicate, and delete Espanso match files
- Create and edit replacement matches, forms, form fields, and variables
- Work with shell, script, form, and choice variables
- Preserve additional supported YAML fields when saving match files
- Edit and validate the complete YAML document in Expert YAML mode
- Restart Espanso directly after saving changes

## Installation

Install [Espanso](https://espanso.org/install/) first. Espanso GUI automatically
locates its `match` directory and edits the same files used by Espanso.

### Debian and Ubuntu

Download the `.deb` file from the project's [Releases](https://github.com/johannjdk/espanso-gui-qt/releases)
page, then install it locally:

```bash
sudo apt install ./espanso-gui-qt_VERSION_all.deb
```

### Arch Linux

Download the `.pkg.tar.*` file from the [Releases](https://github.com/johannjdk/espanso-gui-qt/releases)
page and install it with pacman:

```bash
sudo pacman -U ./espanso-gui-qt-VERSION-any.pkg.tar.zst
```

### Run from source

Requirements: Python 3.10 or newer, PySide6, and PyYAML.

```bash
git clone https://github.com/johannjdk/espanso-gui-qt.git
cd espanso-gui-qt
python -m venv .venv
source .venv/bin/activate
pip install -e .
espanso-gui-qt
```

## How it works

The application discovers Espanso's `match` directory automatically:

- Linux: `~/.config/espanso/match` or `$XDG_CONFIG_HOME/espanso/match`
- macOS: `~/Library/Application Support/espanso/match`
- Windows: `%APPDATA%\\espanso\\match`

Choose a configuration file in the left panel, edit its matches, and click
**Save**. Use **Restart Espanso** when you want Espanso to reload the changes
immediately. Existing YAML is validated before Expert YAML changes are saved.

Run this command from the directory containing both the package and
`SHA256SUMS`.

## Contributing and support

Bug reports and feature requests are welcome in the
[issue tracker](https://github.com/johannjdk/espanso-gui-qt/issues). For a code
change, please open a pull request with a concise description and reproduction
or testing notes where relevant.