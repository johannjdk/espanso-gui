# Espanso GUI Qt

Espanso GUI Qt is a desktop editor for [Espanso](https://espanso.org/) match files. It provides a native Qt interface for managing replacements, forms, variables, and the underlying YAML configuration.

## Requirements

- Python 3.10 or newer
- PySide6
- PyYAML

## Run from source

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
espanso-gui-qt
```

The application discovers Espanso's `match` directory automatically:

- Linux: `~/.config/espanso/match` or `$XDG_CONFIG_HOME/espanso/match`
- macOS: `~/Library/Application Support/espanso/match`
- Windows: `%APPDATA%\\espanso\\match`
