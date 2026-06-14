#!/usr/bin/env python3
import sys
import os
import yaml
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog,
    QFrame, QScrollArea, QSplitter, QMessageBox
)
from PyQt5.QtCore import Qt, QProcess, pyqtSignal, pyqtSlot, QObject, QUrl
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QDesktopServices

class DropZone(QFrame):
    """
    A custom frame that accepts drag and drop events for files, directories,
    and text (e.g. YouTube links) and highlights on hover.
    """
    dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("drop-zone")
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.setMinimumHeight(150)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        
        # Emoji representation of drag and drop
        self.icon_label = QLabel("📥", self)
        self.icon_label.setStyleSheet("font-size: 40px;")
        self.icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_label)
        
        self.text_label = QLabel("Drag & Drop Files, Folders, or YouTube Links Here", self)
        self.text_label.setObjectName("drop-zone-text")
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setWordWrap(True)
        layout.addWidget(self.text_label)

        self.apply_style(dragged=False)

    def apply_style(self, dragged=False):
        if dragged:
            self.setStyleSheet("""
                #drop-zone {
                    background-color: #1a233a;
                    border: 2px solid #00adb5;
                    border-radius: 10px;
                }
                #drop-zone-text {
                    font-size: 14px;
                    color: #00adb5;
                    font-weight: bold;
                }
            """)
        else:
            self.setStyleSheet("""
                #drop-zone {
                    background-color: #1e1e24;
                    border: 2px dashed #4e4e5a;
                    border-radius: 10px;
                }
                #drop-zone-text {
                    font-size: 13px;
                    color: #a0a0b2;
                    font-weight: normal;
                }
            """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
            self.apply_style(dragged=True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.apply_style(dragged=False)

    def dropEvent(self, event):
        self.apply_style(dragged=False)
        
        # Try retrieving URLs first (files and folders)
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                first_url = urls[0]
                local_path = first_url.toLocalFile()
                if local_path:
                    self.dropped.emit(local_path)
                    event.acceptProposedAction()
                    return
                else:
                    self.dropped.emit(first_url.toString())
                    event.acceptProposedAction()
                    return
        
        # Fallback to plain text (URLs from browser address bar)
        if event.mimeData().hasText():
            text = event.mimeData().text().strip()
            if text:
                self.dropped.emit(text)
                event.acceptProposedAction()


class CommandRunner(QObject):
    """
    Asynchronous command runner using QProcess to run scripts in system shells
    without freezing the main Qt UI.
    """
    output_received = pyqtSignal(str, bool)  # text, is_error
    finished = pyqtSignal(int)               # exit code

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None

    def run(self, command_str):
        if self.process and self.process.state() != QProcess.NotRunning:
            return False

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.handle_finished)

        # Execute inside a system shell wrapper for pipeline and system utilities support
        if os.name == 'nt':
            shell = "cmd.exe"
            args = ["/c", command_str]
        else:
            shell = "/bin/sh"
            args = ["-c", command_str]

        self.process.start(shell, args)
        return True

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data()
        self.output_received.emit(self.decode(data), False)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data()
        self.output_received.emit(self.decode(data), True)

    def decode(self, data):
        for encoding in ('utf-8', 'latin1', 'cp1252'):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return str(data)

    def handle_finished(self, exit_code, exit_status):
        self.finished.emit(exit_code)

    def stop(self):
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(1000):
                self.process.kill()


class MainWindow(QMainWindow):
    def __init__(self, config_path):
        super().__init__()
        self.config_path = os.path.abspath(config_path)
        self.runner = CommandRunner(self)
        self.runner.output_received.connect(self.on_runner_output)
        self.runner.finished.connect(self.on_runner_finished)
        self.scripts = []
        self.batch_items = []
        self.batch_index = 0
        self.current_batch_script = None

        self.setWindowTitle("Cross-Platform Qt Script Launcher")
        self.resize(900, 650)
        self.init_ui()
        self.load_config()
        self.apply_global_style()

    def init_ui(self):
        # Central widget and layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Splitter to allow resizing panels
        splitter = QSplitter(Qt.Horizontal, self)
        main_layout.addWidget(splitter)

        # ================= LEFT SIDEBAR (SCRIPTS) =================
        sidebar = QWidget(self)
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_layout.setSpacing(10)

        # Sidebar title
        sidebar_title = QLabel("Trigger Scripts", sidebar)
        sidebar_title.setObjectName("sidebar-title")
        sidebar_layout.addWidget(sidebar_title)

        # Scroll area for script buttons
        scroll = QScrollArea(sidebar)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("scroll-area")
        
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("scroll-content")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(8)
        self.scroll_layout.addStretch()  # Stretch pushed buttons to top
        
        scroll.setWidget(self.scroll_content)
        sidebar_layout.addWidget(scroll)

        # ================= RIGHT PANEL (MAIN WORKSPACE) =================
        workspace = QWidget(self)
        workspace.setObjectName("workspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(20, 20, 20, 20)
        workspace_layout.setSpacing(15)

        # Top Bar (Header + Config Actions)
        top_bar = QHBoxLayout()
        title_container = QVBoxLayout()
        
        app_title = QLabel("Script Launcher & Drag-Drop Runner", workspace)
        app_title.setObjectName("app-title")
        title_container.addWidget(app_title)
        
        app_subtitle = QLabel("Drag files or links, then trigger configured scripts.", workspace)
        app_subtitle.setObjectName("app-subtitle")
        title_container.addWidget(app_subtitle)
        
        top_bar.addLayout(title_container)
        top_bar.addStretch()

        btn_edit_config = QPushButton("📝 Edit Config", workspace)
        btn_edit_config.setObjectName("btn-secondary")
        btn_edit_config.clicked.connect(self.edit_config)
        top_bar.addWidget(btn_edit_config)

        btn_reload_config = QPushButton("🔄 Reload Config", workspace)
        btn_reload_config.setObjectName("btn-secondary")
        btn_reload_config.clicked.connect(self.load_config)
        top_bar.addWidget(btn_reload_config)

        workspace_layout.addLayout(top_bar)

        # Drag and Drop Area
        self.drop_zone = DropZone(workspace)
        self.drop_zone.dropped.connect(self.on_item_dropped)
        workspace_layout.addWidget(self.drop_zone)

        # Input Area (File / Link display)
        input_container = QHBoxLayout()
        
        self.input_edit = QLineEdit(workspace)
        self.input_edit.setPlaceholderText("Current Input File Path or URL...")
        self.input_edit.setObjectName("input-field")
        input_container.addWidget(self.input_edit)

        btn_browse_file = QPushButton("📁 File...", workspace)
        btn_browse_file.setObjectName("btn-action")
        btn_browse_file.clicked.connect(self.browse_file)
        input_container.addWidget(btn_browse_file)

        btn_browse_dir = QPushButton("📂 Folder...", workspace)
        btn_browse_dir.setObjectName("btn-action")
        btn_browse_dir.clicked.connect(self.browse_directory)
        input_container.addWidget(btn_browse_dir)

        workspace_layout.addLayout(input_container)

        self.batch_label = QLabel("", workspace)
        self.batch_label.setObjectName("batch-label")
        self.batch_label.setVisible(False)
        workspace_layout.addWidget(self.batch_label)

        # Divider line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #2e2e36; height: 1px; border: none;")
        workspace_layout.addWidget(line)

        # Console / Terminal Log Output
        console_header = QHBoxLayout()
        console_title = QLabel("Console Output Log", workspace)
        console_title.setObjectName("console-title")
        console_header.addWidget(console_title)
        
        self.status_dot = QLabel("●", workspace)
        self.status_dot.setStyleSheet("color: #4caf50; font-size: 14px;") # Green dot
        console_header.addWidget(self.status_dot)
        
        self.status_label = QLabel("Status: IDLE", workspace)
        self.status_label.setObjectName("status-text")
        console_header.addWidget(self.status_label)
        console_header.addStretch()

        self.btn_stop = QPushButton("⏹️ Stop Script", workspace)
        self.btn_stop.setObjectName("btn-danger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_current_script)
        console_header.addWidget(self.btn_stop)

        self.btn_clear_log = QPushButton("🗑️ Clear Log", workspace)
        self.btn_clear_log.setObjectName("btn-secondary-sm")
        self.btn_clear_log.clicked.connect(self.clear_console)
        console_header.addWidget(self.btn_clear_log)

        workspace_layout.addLayout(console_header)

        self.console = QTextEdit(workspace)
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Console logs will appear here when a script runs...")
        workspace_layout.addWidget(self.console)

        # Add to Splitter
        splitter.addWidget(sidebar)
        splitter.addWidget(workspace)
        
        # Set default proportions: sidebar takes ~30%, workspace ~70%
        splitter.setSizes([270, 630])

    def apply_global_style(self):
        self.setStyleSheet("""
            /* Main Window */
            QMainWindow {
                background-color: #121214;
            }

            /* Widget Defaults */
            QWidget {
                color: #e1e1e6;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
                font-size: 13px;
            }

            /* Left Sidebar container */
            #sidebar {
                background-color: #1a1a1e;
                border-right: 1px solid #2e2e36;
            }

            #sidebar-title {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                padding-bottom: 5px;
                border-bottom: 2px solid #00adb5;
            }

            /* Main Workspace container */
            #workspace {
                background-color: #121214;
            }

            #app-title {
                font-size: 18px;
                font-weight: bold;
                color: #ffffff;
            }

            #app-subtitle {
                font-size: 12px;
                color: #a0a0b2;
            }

            /* Input Line Edit */
            #input-field {
                background-color: #1e1e24;
                border: 1px solid #2e2e36;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 13px;
                selection-background-color: #00adb5;
            }
            #input-field:focus {
                border: 1px solid #00adb5;
            }

            /* Base buttons */
            QPushButton {
                background-color: #252836;
                border: 1px solid #2e303e;
                border-radius: 6px;
                padding: 8px 14px;
                color: #eeeeee;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2e3248;
                border: 1px solid #00adb5;
            }
            QPushButton:pressed {
                background-color: #1f2232;
            }
            QPushButton:disabled {
                background-color: #1c1c20;
                color: #6e6e7c;
                border: 1px solid #25252b;
            }

            /* Action Buttons (browse etc) */
            #btn-action {
                background-color: #222226;
                border: 1px solid #2e2e36;
            }
            #btn-action:hover {
                background-color: #2a2a32;
                border: 1px solid #3e3e4d;
            }

            /* Secondary control buttons */
            #btn-secondary {
                background-color: #1a1a1e;
                border: 1px solid #2e2e36;
                padding: 6px 12px;
                font-weight: normal;
                font-size: 12px;
            }
            #btn-secondary:hover {
                background-color: #222226;
                border: 1px solid #00adb5;
            }

            #btn-secondary-sm {
                background-color: #1a1a1e;
                border: 1px solid #2e2e36;
                padding: 4px 8px;
                font-weight: normal;
                font-size: 11px;
            }
            #btn-secondary-sm:hover {
                background-color: #222226;
                border: 1px solid #ff9800;
            }

            /* Danger stop button */
            #btn-danger {
                background-color: #3f1f22;
                border: 1px solid #5a2e32;
                padding: 4px 10px;
                color: #ff8a8a;
                font-size: 11px;
            }
            #btn-danger:hover {
                background-color: #55252a;
                border: 1px solid #f44336;
            }
            #btn-danger:disabled {
                background-color: #1c1c20;
                color: #6e6e7c;
                border: 1px solid #25252b;
            }

            /* Monospace Console */
            #console {
                background-color: #0c0c0e;
                border: 1px solid #2e2e36;
                border-radius: 8px;
                font-family: 'Fira Code', 'Cascadia Code', Consolas, Monaco, Courier New, monospace;
                font-size: 12px;
                padding: 10px;
            }

            #console-title {
                font-weight: bold;
                font-size: 14px;
                color: #ffffff;
            }

            #status-text {
                font-size: 12px;
                color: #a0a0b2;
            }

            #batch-label {
                font-size: 12px;
                color: #00adb5;
                padding: 2px 0px;
            }

            /* Dynamic Script List Buttons */
            .script-btn {
                background-color: #222228;
                border: 1px solid #2e2e36;
                border-radius: 8px;
                text-align: left;
                padding: 12px;
            }
            .script-btn:hover {
                background-color: #2a2a38;
                border: 1px solid #00adb5;
            }
            .script-btn-title {
                font-weight: bold;
                color: #ffffff;
                font-size: 13px;
            }
            .script-btn-desc {
                color: #8c8c9e;
                font-size: 11px;
                margin-top: 4px;
            }
        """)

    def load_config(self):
        # Clear existing buttons
        while self.scroll_layout.count() > 1:
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Check if file exists
        if not os.path.exists(self.config_path):
            self.create_default_config()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                
            self.scripts = data.get('scripts', [])
            if not isinstance(self.scripts, list):
                raise ValueError("The 'scripts' element in YAML must be a list.")
                
        except Exception as e:
            QMessageBox.warning(
                self, 
                "Config File Error", 
                f"Could not parse config.yml correctly:\n{str(e)}\n\nFalling back to default scripts."
            )
            self.scripts = self.get_default_scripts()

        # Build UI buttons for scripts
        for index, script in enumerate(self.scripts):
            name = script.get('name', 'Unnamed Script')
            desc = script.get('description', '')
            cmd = script.get('command', '')
            
            btn = QPushButton(self.scroll_content)
            btn.setObjectName(f"script-btn-{index}")
            btn.setProperty("class", "script-btn")
            btn.setCursor(Qt.PointingHandCursor)
            
            btn_layout = QVBoxLayout(btn)
            btn_layout.setContentsMargins(6, 6, 6, 6)
            btn_layout.setSpacing(2)
            
            lbl_title = QLabel(name, btn)
            lbl_title.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 13px; background: transparent;")
            lbl_title.setAttribute(Qt.WA_TranslucentBackground)
            btn_layout.addWidget(lbl_title)
            
            if desc:
                lbl_desc = QLabel(desc, btn)
                lbl_desc.setStyleSheet("color: #8c8c9e; font-size: 11px; background: transparent;")
                lbl_desc.setAttribute(Qt.WA_TranslucentBackground)
                lbl_desc.setWordWrap(True)
                btn_layout.addWidget(lbl_desc)
                
            btn.setToolTip(f"Command:\n{cmd}")
            
            btn.clicked.connect(lambda checked, idx=index: self.run_script(idx))
            self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, btn)

        self.append_info_log(f"Successfully loaded {len(self.scripts)} scripts from config.")

    def create_default_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        default_data = {
            'scripts': self.get_default_scripts()
        }
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_data, f, default_flow_style=False)
        except Exception as e:
            self.append_err_log(f"Error creating default config file: {str(e)}")

    def get_default_scripts(self):
        return [
            {
                'name': 'Print Target Details',
                'command': "echo '--- Target Info ---' && echo 'Full input: {input}' && echo 'Directory: {dirname}' && echo 'Filename: {filename}' && echo 'Base: {basename}'",
                'description': 'Displays all substituted placeholders for the current target.'
            },
            {
                'name': 'Show Directory Contents',
                'command': "ls -lh '{dirname}'",
                'description': 'List the contents of the parent directory of the selected file.'
            },
            {
                'name': 'Show File Type',
                'command': "file '{input}'",
                'description': 'Runs the Linux "file" command on the input path.'
            }
        ]

    def edit_config(self):
        """Open the config file in the default OS application/editor"""
        if not os.path.exists(self.config_path):
            self.create_default_config()
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.config_path))

    def _try_load_batch(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f if l.strip() and not l.strip().startswith('#')]
            return lines if len(lines) >= 2 else None
        except Exception:
            return None

    def _update_batch_label(self):
        if self.batch_items:
            self.batch_label.setText(f"Batch mode: {len(self.batch_items)} items loaded")
            self.batch_label.setVisible(True)
        else:
            self.batch_label.setVisible(False)

    def _set_input(self, value):
        self.input_edit.setText(value)
        self.batch_items = []
        self.batch_index = 0
        if os.path.isfile(value):
            batch = self._try_load_batch(value)
            if batch:
                self.batch_items = batch
        self._update_batch_label()

    @pyqtSlot(str)
    def on_item_dropped(self, text):
        self._set_input(text)
        if self.batch_items:
            self.append_info_log(f"Batch list loaded from: {text} ({len(self.batch_items)} items)")
        else:
            self.append_info_log(f"Input target set to: {text}")

    def browse_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select File")
        if file_name:
            self._set_input(file_name)
            if self.batch_items:
                self.append_info_log(f"Batch list loaded from: {file_name} ({len(self.batch_items)} items)")
            else:
                self.append_info_log(f"Input target set to file: {file_name}")

    def browse_directory(self):
        dir_name = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_name:
            self._set_input(dir_name)
            self.append_info_log(f"Input target set to directory: {dir_name}")

    def run_script(self, index):
        if self.batch_items:
            self.batch_index = 0
            self.current_batch_script = index
            self.clear_console()
            self.append_info_log(
                f"Starting batch run: {len(self.batch_items)} items\n" + "-" * 60
            )
            self._run_single(self.batch_items[0], index)
        else:
            input_target = self.input_edit.text().strip()
            if not input_target:
                QMessageBox.information(
                    self,
                    "No Input Target",
                    "Please drag & drop a file/link or click File/Folder to choose a target first."
                )
                return
            self.current_batch_script = None
            self.clear_console()
            self._run_single(input_target, index)

    def _run_single(self, input_target, index):
        if index >= len(self.scripts):
            return

        script = self.scripts[index]
        cmd_template = script.get('command', '')
        script_name = script.get('name', 'Script')

        is_local_path = os.path.exists(input_target) or (
            not input_target.startswith("http://") and
            not input_target.startswith("https://") and
            os.path.isabs(input_target)
        )

        if is_local_path:
            abspath = os.path.abspath(input_target)
            dirname = os.path.dirname(abspath)
            filename = os.path.basename(abspath)
            basename, _ = os.path.splitext(filename)
        else:
            abspath = input_target
            dirname = os.getcwd()
            filename = input_target
            basename = input_target

        placeholders = {
            "input": abspath,
            "dirname": dirname,
            "filename": filename,
            "basename": basename
        }

        command = cmd_template
        for key, val in placeholders.items():
            command = command.replace(f"{{{key}}}", val)

        self.append_info_log(f"Starting Script: {script_name}")
        self.append_info_log(f"Command: {command}\n" + "-" * 60 + "\n")

        self.set_ui_running_state(True)

        success = self.runner.run(command)
        if not success:
            self.append_err_log("Failed to start process. Is another script already running?")
            self.set_ui_running_state(False)

    def set_ui_running_state(self, running):
        for btn in self.scroll_content.findChildren(QPushButton):
            btn.setEnabled(not running)
            
        self.input_edit.setEnabled(not running)
        
        if running:
            self.btn_stop.setEnabled(True)
            self.status_dot.setStyleSheet("color: #ff9800; font-size: 14px;") # Yellow dot (busy)
            self.status_label.setText("Status: RUNNING")
        else:
            self.btn_stop.setEnabled(False)
            self.status_dot.setStyleSheet("color: #4caf50; font-size: 14px;") # Green dot (idle)
            self.status_label.setText("Status: IDLE")

    @pyqtSlot(str, bool)
    def on_runner_output(self, text, is_error):
        self.append_console_text(text, is_error)

    @pyqtSlot(int)
    def on_runner_finished(self, exit_code):
        self.append_info_log(f"\n" + "-" * 60)
        if exit_code == 0:
            self.append_info_log("Process finished successfully (exit code 0).")
        else:
            self.append_err_log(f"Process exited with non-zero code: {exit_code}")

        if self.batch_items and self.current_batch_script is not None:
            self.batch_index += 1
            if self.batch_index < len(self.batch_items):
                next_item = self.batch_items[self.batch_index]
                self.append_info_log(
                    f"\nBatch progress: item {self.batch_index + 1}/{len(self.batch_items)}\n" + "-" * 60
                )
                self._run_single(next_item, self.current_batch_script)
                return
            else:
                self.append_info_log(
                    f"\nBatch complete: {len(self.batch_items)} items processed."
                )

        self.set_ui_running_state(False)

    def stop_current_script(self):
        self.batch_index = 0
        self.current_batch_script = None
        self.append_err_log("\n[User requested abort... Terminating process]")
        self.runner.stop()

    def clear_console(self):
        self.console.clear()

    def append_console_text(self, text, is_error=False):
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.console.setTextCursor(cursor)
        
        fmt = QTextCharFormat()
        if is_error:
            fmt.setForeground(QColor("#f44336"))  # Soft red for error output
        else:
            fmt.setForeground(QColor("#a8ffb2"))  # Soft green for stdout
            
        cursor.insertText(text, fmt)
        
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def append_info_log(self, text):
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.console.setTextCursor(cursor)
        
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#ffffff"))  # White for info messages
        
        cursor.insertText(text + "\n", fmt)
        
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def append_err_log(self, text):
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.console.setTextCursor(cursor)
        
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#ff5722"))  # Orange-red for launcher warnings
        fmt.setFontWeight(QFont.Bold)
        
        cursor.insertText(text + "\n", fmt)
        
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(base_dir, "config.yml")
    
    app = QApplication(sys.argv)
    
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    window = MainWindow(config_file)
    window.show()
    sys.exit(app.exec_())
