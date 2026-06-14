# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
python3 main.py
```

Dependencies must be installed first:

```bash
# System packages (Ubuntu/Debian)
sudo apt install python3-pyqt5 python3-yaml

# Or via pip in a venv
python3 -m venv ./
. bin/activate
pip3 install PyQt5 PyYAML
```

There are no tests and no build step — the app runs directly.

## Architecture

The entire application lives in a single file (`main.py`) with three classes:

- **`DropZone(QFrame)`** — the drag-and-drop target widget. Emits a `dropped(str)` signal with either a local filesystem path (extracted via `toLocalFile()`) or a raw URL string. Handles both file-manager drags (MIME URLs) and browser address-bar drags (plain text fallback).

- **`CommandRunner(QObject)`** — wraps `QProcess` to run shell commands asynchronously. Pipes stdout/stderr back via `output_received(str, bool)` signals, which keeps the UI responsive. Uses `/bin/sh -c` on Unix, `cmd.exe /c` on Windows. Only one process runs at a time; `stop()` terminates then kills if needed.

- **`MainWindow(QMainWindow)`** — owns the `CommandRunner` and the overall layout (left sidebar of script buttons + right workspace with drop zone, input field, and console). Script buttons are built dynamically from `config.yml` in `load_config()`. Placeholder substitution (`{input}`, `{dirname}`, `{filename}`, `{basename}`) happens in `run_script()` just before handing the command string to `CommandRunner`.

## config.yml

Scripts are defined under a `scripts:` list. Each entry has `name`, `command`, and `description`. The four placeholders are substituted at run time; for URLs (non-local paths), `{dirname}` falls back to `os.getcwd()` and `{filename}`/`{basename}` are set to the raw URL string.

The config file is loaded at startup and on "Reload Config" clicks. If the file is missing, a default is auto-created. Parse errors fall back to a built-in default script list.

## Console Color Conventions

| Color | Meaning |
|---|---|
| Green (`#a8ffb2`) | stdout from the subprocess |
| Red (`#f44336`) | stderr from the subprocess |
| White | Launcher info messages |
| Orange-red (`#ff5722`) | Launcher warnings/errors |
