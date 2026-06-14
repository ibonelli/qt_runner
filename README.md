# Cross-Platform Qt Script Launcher (QTrunner)

A modern, dark-themed **PyQt5** desktop application for Windows and Linux. It features a drag-and-drop workspace where you can drop files, folders, or web links (like YouTube links) and trigger custom command-line scripts configured via a YAML file (`config.yml`).

## Features
- **Drag & Drop UI**: Accepting local files, directories, and web URLs (e.g. YouTube links).
- **Asynchronous Script Execution**: Scripts run in native system shells without blocking or freezing the application's graphical user interface.
- **Real-time Console Output**: View `stdout` (in green) and `stderr` (in red) outputs as they print.
- **Configurable YAML Buttons**: Easily add, delete, or modify scripts in `config.yml`.
- **Dynamic Reloading**: Click the "Reload Config" button to update buttons instantly, or click "Edit Config" to open the configuration in your default system text editor.
- **Process Termination**: Safely abort long-running scripts (e.g. downloads) using the "Stop Script" button.
- **File Browser Backups**: Traditional file and directory dialogs if drag-and-drop is not preferred.

---

## Installation & Prerequisites

To run this application, you must have Python 3 and the required dependencies installed on your system.

### Dependencies
1. **PyQt5** (UI framework)
2. **PyYAML** (YAML parser)

#### Installing on Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3-pip python3-pyqt5 python3-yaml
```
*Alternatively, using pip:*
```bash
python3 -m venv ./
. bin/activate
pip3 install PyQt5 PyYAML
```

## Running the Application

Navigate to the project directory and run:
```bash
python3 main.py
```
*(On Windows, you can also run `python main.py` or double-click `main.py` if python files are associated with the python launcher).*

---

## Configuring Scripts (`config.yml`)

The configuration file is dynamically loaded when the application starts. Buttons are drawn automatically on the left sidebar.

### Placeholders
You can use the following curly-bracket placeholders in your script commands:
- `{input}`: The absolute path of the dropped item, or the URL/text string itself.
- `{filename}`: The filename with extension (e.g. `document.pdf`). If the input is a URL, this will be the URL.
- `{basename}`: The filename without its extension (e.g. `document`).
- `{dirname}`: The path to the parent directory (e.g. `/home/user/Downloads`). If the input is a URL, this defaults to the current working directory of the application.

### Example YAML Schema
```yaml
scripts:
  - name: "Print Target Details"
    command: "echo '--- Target Info ---' && echo 'Full input: {input}' && echo 'Directory: {dirname}' && echo 'Filename: {filename}' && echo 'Base: {basename}'"
    description: "Displays all substituted placeholders for the current target."

  - name: "Convert Video to MP4"
    command: "ffmpeg -i '{input}' -c:v libx264 -crf 23 -c:a aac -q:a 100 '{dirname}/{basename}_converted.mp4'"
    description: "Converts drag-and-drop video file to MP4 format using ffmpeg (requires ffmpeg installed)."

  - name: "Download YouTube MP3"
    command: "yt-dlp -x --audio-format mp3 -o '%(title)s.%(ext)s' '{input}'"
    description: "Downloads the audio tracks from a YouTube link using yt-dlp (requires yt-dlp installed)."
```

---

## How It Works Under the Hood

1. **Mime Detection**: The drag-and-drop container (`DropZone`) subclasses `QFrame` and intercepts `dragEnterEvent` and `dropEvent`. It inspects URLs to extract local file paths using `toLocalFile()` and falls back to string parsing for browser-dragged URLs.
2. **Process Wrapper**: A custom `CommandRunner` subclasses `QObject` and holds a `QProcess`. It fires the command string through the system shell (`/bin/sh` on Unix-like platforms and `cmd.exe` on Windows).
3. **Responsive GUI**: Standard output and error buffers are piped using asynchronous Qt signals, which write to a custom colored terminal control (`QTextEdit` with `QTextCharFormat`).
# qt_runner
