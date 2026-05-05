import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)

from config import APP_VERSION, get_config_path
from workers import LyricFetchWorker, IconFetchWorker, PyphenLoadWorker
from ui_components import AboutDialog, WordInputDialog, ConfigEditor, LyricTextEdit
from exporters import generate_kbp_content, export_auto_files
from processor import sanitize_lyrics_text, auto_split_text, calculate_live_sync

class StreamlinedLyricApp(QMainWindow):
    def __init__(self, cli_args=None):
        super().__init__()

        if getattr(sys, "frozen", False):
            self.app_path = str(getattr(sys, "_MEIPASS", ""))
            self.exe_dir = os.path.dirname(sys.executable)
        else:
            self.app_path = os.path.dirname(__file__)
            self.exe_dir = self.app_path

        self.config_path = get_config_path()

        self.trip_ups: dict[str, str] = {}
        self.false_positives: set[str] = set()

        self.load_config()

        self.dic = None # Loaded asynchronously
        self.history = []
        self.pre_keypress_snapshot = ""

        # CLI Arguments initialization
        self.cli_args = cli_args or argparse.Namespace(
            artist="", song="", audio="", out="", auto=False, silent=False, edit=""
        )
        if self.cli_args.silent:
            self.cli_args.auto = True

        self.is_auto_processing = False
        self.audio_path = self.cli_args.audio
        self.out_dir = self.cli_args.out

        self.setWindowTitle(f"Local Lyric Splitter v{APP_VERSION}")
        self.resize(1000, 800)

        self.lang_profiles = {
            "English": {"flag": "us", "pyphen": "en_US", "threshold": 5},
            "Spanish": {"flag": "mx", "pyphen": "es", "threshold": 6},
            "French": {"flag": "fr", "pyphen": "fr_FR", "threshold": 7},
            "German": {"flag": "de", "pyphen": "de_DE", "threshold": 10},
            "Russian": {"flag": "ru", "pyphen": "ru_RU", "threshold": 7},
        }
        self.current_lang_name = "English"

        self.highlight_threshold: int = int(
            self.lang_profiles[self.current_lang_name]["threshold"]
        )

        self.apply_global_styles()
        self.set_app_icon()

        # Create Top Menu Bar natively
        self.menu_bar = self.menuBar()

        # File Menu
        self.file_menu = self.menu_bar.addMenu("File")
        open_action = QAction("Open .txt File", self)
        open_action.triggered.connect(self.import_from_txt)
        self.file_menu.addAction(open_action)

        save_action = QAction("Save as .txt", self)
        save_action.triggered.connect(self.export_to_txt)
        self.file_menu.addAction(save_action)

        export_kbp_action = QAction("Export as .kbp", self)
        export_kbp_action.triggered.connect(self.manual_export_kbp)
        self.file_menu.addAction(export_kbp_action)

        self.file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)

        # Settings Menu
        self.settings_menu = self.menu_bar.addMenu("Settings")
        config_action = QAction("Configuration Editor", self)
        config_action.triggered.connect(self.open_editor)
        self.settings_menu.addAction(config_action)

        # Help Menu
        self.help_menu = self.menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.open_about)
        self.help_menu.addAction(about_action)

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        self.header_frame = QHBoxLayout()

        self.artist_input = QLineEdit()
        self.artist_input.setPlaceholderText("Artist Name...")
        self.artist_input.setFixedWidth(200)
        if self.cli_args.artist:
            self.artist_input.setText(self.cli_args.artist)

        self.song_input = QLineEdit()
        self.song_input.setPlaceholderText("Song Title...")
        self.song_input.setFixedWidth(250)
        if self.cli_args.song:
            self.song_input.setText(self.cli_args.song)

        self.fetch_btn = QPushButton("Fetch Lyrics")
        self.fetch_btn.setStyleSheet(
            "background-color: #1f538d; color: white; font-weight: bold; padding: 4px 10px;"
        )
        self.fetch_btn.clicked.connect(self.start_lyric_fetch)

        self.auto_process_btn = QPushButton("Auto-Process")
        self.auto_process_btn.setStyleSheet(
            "background-color: #2c5d3f; color: white; font-weight: bold; padding: 4px 10px;"
        )
        self.auto_process_btn.clicked.connect(self.start_auto_process)

        self.source_label = QLabel("")
        self.source_label.setStyleSheet(
            "color: #aaaaaa; font-style: italic; padding-left: 10px;"
        )

        self.header_frame.addWidget(QLabel("<b>Fetch:</b>"))
        self.header_frame.addWidget(self.artist_input)
        self.header_frame.addWidget(self.song_input)
        self.header_frame.addWidget(self.fetch_btn)
        self.header_frame.addWidget(self.auto_process_btn)
        self.header_frame.addWidget(self.source_label)

        self.header_frame.addStretch()

        self.lang_menu = QComboBox()
        self.lang_menu.setIconSize(QSize(20, 15))
        self.lang_menu.setMinimumWidth(150)
        self.header_frame.addWidget(self.lang_menu)
        self.main_layout.addLayout(self.header_frame)

        # Populate lang menu and fetch icons asynchronously
        self.load_flag_icons()

        self.lang_menu.currentTextChanged.connect(self.change_language)

        # Editor
        self.txt = LyricTextEdit(self)
        self.main_layout.addWidget(self.txt)

        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self.undo)

        self.control_bar = QHBoxLayout()

        self.highlight_var = QCheckBox("Highlighting")
        self.highlight_var.setChecked(True)
        self.highlight_var.stateChanged.connect(self.refresh_highlights)
        self.control_bar.addWidget(self.highlight_var)

        self.add_control_btn("Sanitize", "#721c24", self.sanitize_lyrics)
        self.add_control_btn("Auto-Split", "#2c5d3f", self.auto_split)

        self.copy_btn = QPushButton("Copy Lyrics")
        self.copy_btn.setStyleSheet(
            "background-color: #1f538d; color: white; font-weight: bold; padding: 6px;"
        )
        self.copy_btn.setMinimumWidth(110)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        self.control_bar.addWidget(self.copy_btn)

        self.add_control_btn("Config", "#444", self.open_editor)
        self.add_control_btn("About", "#444", self.open_about)

        self.control_bar.addStretch()

        self.add_control_btn("Undo", "#721c24", self.undo)

        self.main_layout.addLayout(self.control_bar)

        if getattr(self.cli_args, "edit", "") and os.path.exists(self.cli_args.edit):
            try:
                with open(self.cli_args.edit, "r", encoding="utf-8") as f:
                    content = f.read()
                self.take_snapshot()
                self.txt.setPlainText(content)
                self.refresh_highlights()
            except Exception:
                pass

        # Load initial dictionary
        self.change_language(self.current_lang_name)

        if self.cli_args.auto:
            QTimer.singleShot(500, self.start_auto_process)

    def load_flag_icons(self):
        config_dir = os.path.dirname(self.config_path)
        flags_dir = os.path.join(config_dir, "flags")
        os.makedirs(flags_dir, exist_ok=True)
        
        self.icon_workers = []
        for lang_name, profile in self.lang_profiles.items():
            self.lang_menu.addItem(lang_name)
            country_code = profile["flag"]
            icon_path = os.path.join(flags_dir, f"{country_code}.png")
            worker = IconFetchWorker(country_code, icon_path)
            worker.success.connect(lambda cc, path, ln=lang_name: self.on_icon_loaded(cc, path, ln))
            self.icon_workers.append(worker)
            worker.start()

    def on_icon_loaded(self, country_code, icon_path, lang_name):
        icon = QIcon(icon_path)
        index = self.lang_menu.findText(lang_name)
        if index >= 0:
            self.lang_menu.setItemIcon(index, icon)

    def start_lyric_fetch(self):
        artist = self.artist_input.text()
        song = self.song_input.text()
        if not artist or not song:
            if not self.cli_args.silent:
                QMessageBox.warning(
                    self, "Input Required", "Please enter both Artist and Song Title."
                )
            elif self.cli_args.auto:
                QApplication.quit()
            return

        self.source_label.setText("")
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Searching...")

        self.worker = LyricFetchWorker(artist, song)
        self.worker.success.connect(self.on_fetch_success)
        self.worker.failure.connect(self.on_fetch_error)
        self.worker.start()

    def on_fetch_success(self, lyrics, source):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch Lyrics")
        self.source_label.setText(f"Source: {source}")
        self.take_snapshot()
        self.txt.setPlainText(lyrics)
        self.sanitize_lyrics()
        self.refresh_highlights()

        if getattr(self, "is_auto_processing", False):
            self.auto_split()
            self.do_export_auto_files()
            self.is_auto_processing = False

    def on_fetch_error(self, message):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch Lyrics")
        self.source_label.setText("Source: None")
        self.is_auto_processing = False
        if not self.cli_args.silent:
            QMessageBox.warning(self, "Not Found", message)

        if self.cli_args.auto:
            QApplication.quit()

    def start_auto_process(self):
        artist = self.artist_input.text()
        song = self.song_input.text()
        if not artist or not song:
            if not self.cli_args.silent:
                QMessageBox.warning(
                    self, "Input Required", "Please enter both Artist and Song Title."
                )
            if self.cli_args.auto:
                QApplication.quit()
            return

        if not self.audio_path:
            if self.cli_args.silent:
                if self.cli_args.auto:
                    QApplication.quit()
                return
            audio_file, _ = QFileDialog.getOpenFileName(
                self,
                "Select Audio File for Sync",
                "",
                "Audio Files (*.mp3 *.wav *.ogg *.flac);;All Files (*.*)",
            )
            if not audio_file:
                return
            self.audio_path = audio_file

        if not self.out_dir:
            if self.cli_args.silent:
                if self.cli_args.auto:
                    QApplication.quit()
                return
            out_directory = QFileDialog.getExistingDirectory(
                self, "Select Save Location"
            )
            if not out_directory:
                return
            self.out_dir = out_directory

        self.is_auto_processing = True
        self.start_lyric_fetch()

    def do_export_auto_files(self):
        artist = self.artist_input.text()
        song = self.song_input.text()
        content = self.txt.toPlainText()
        try:
            txt_path, kbp_path = export_auto_files(artist, song, self.out_dir, content, self.audio_path)
            if self.cli_args.auto:
                QApplication.quit()
            elif not self.cli_args.silent:
                QMessageBox.information(
                    self,
                    "Auto-Process Complete",
                    f"Successfully exported:\n{txt_path}\n{kbp_path}",
                )
        except Exception as e:
            if not self.cli_args.silent:
                QMessageBox.critical(
                    self, "Export Failed", f"Failed to save files: {e}"
                )
            if self.cli_args.auto:
                QApplication.quit()

    def manual_export_kbp(self):
        content = self.txt.toPlainText()
        if not content.strip():
            QMessageBox.warning(self, "Empty", "There are no lyrics to export!")
            return

        audio_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File for KBP Header",
            "",
            "Audio Files (*.mp3 *.wav *.ogg *.flac);;All Files (*.*)",
        )
        if not audio_file:
            return

        artist = self.artist_input.text().strip()
        song = self.song_input.text().strip()
        default_name = (
            f"{artist} - {song}.kbp" if artist and song else "unsynchronized.kbp"
        )

        kbp_path, _ = QFileDialog.getSaveFileName(
            self, "Save Unsynchronized KBP", default_name, "KBP Files (*.kbp)"
        )

        if kbp_path:
            try:
                kbp_content = generate_kbp_content(
                    song if song else "Unknown Title",
                    artist if artist else "Unknown Artist",
                    audio_file,
                    content,
                )

                with open(kbp_path, "w", encoding="utf-8-sig") as f:
                    f.write(kbp_content)

                QMessageBox.information(
                    self, "Success", f"KBP exported to:\n{kbp_path}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save KBP: {e}")

    def add_control_btn(self, text, color, command):
        btn = QPushButton(text)
        btn.setStyleSheet(
            f"background-color: {color}; color: white; font-weight: bold; padding: 6px;"
        )
        btn.setMinimumWidth(110)
        btn.clicked.connect(command)
        self.control_bar.addWidget(btn)

    def apply_global_styles(self):
        app_instance = QApplication.instance()
        if isinstance(app_instance, QApplication):
            app_instance.setStyleSheet("""
                QMainWindow, QDialog { background-color: #242424; color: #e0e0e0; }

                QLabel, QCheckBox { color: #e0e0e0; background-color: transparent; }

                QTextEdit { background-color: #1e1e1e; color: #ffffff; border: 1px solid #333; }
                QLineEdit { background-color: #333; color: white; border: 1px solid #555; padding: 4px; }

                QMenuBar { background-color: #242424; color: white; border-bottom: 1px solid #333; }
                QMenuBar::item { padding: 6px 12px; background: transparent; }
                QMenuBar::item:selected { background-color: #1f538d; border-radius: 4px; }

                QMenu { background-color: #2b2b2b; color: white; border: 1px solid #444; padding: 4px; }
                QMenu::item { padding: 6px 25px 6px 20px; border-radius: 4px; }
                QMenu::item:selected { background-color: #1f538d; }

                QComboBox { background-color: #333; color: white; border: 1px solid #555; padding: 4px; }

                QPushButton { background-color: #444; color: white; border: none; border-radius: 4px; padding: 6px 12px; }
                QPushButton:hover { background-color: #555; }
            """)

    def set_app_icon(self):
        icon_path = os.path.join(self.app_path, "assets", "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(self.app_path, "assets", "about_logo.png")

        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)

            app_instance = QApplication.instance()
            if isinstance(app_instance, QApplication):
                app_instance.setWindowIcon(app_icon)

    def change_language(self, selected_name):
        profile = self.lang_profiles.get(selected_name)
        if profile:
            self.current_lang_name = selected_name
            self.highlight_threshold = int(profile["threshold"])
            
            # Load Pyphen async
            self.pyphen_worker = PyphenLoadWorker(profile["pyphen"])
            self.pyphen_worker.success.connect(self.on_pyphen_loaded)
            self.pyphen_worker.start()

    def on_pyphen_loaded(self, dic):
        self.dic = dic
        self.refresh_highlights()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                try:
                    config = json.load(f)

                    raw_trip_ups = config.get("trip_up_words", {})
                    self.trip_ups = {
                        str(k): str(v) for k, v in sorted(raw_trip_ups.items())
                    }

                    raw_false_pos = config.get("false_positives", [])
                    self.false_positives = {str(word) for word in raw_false_pos}
                except json.JSONDecodeError:
                    self.trip_ups = {}
                    self.false_positives = set()
        else:
            self.trip_ups = {}
            self.false_positives = set()

    def save_config_to_disk(self):
        data = {
            "trip_up_words": dict(sorted(self.trip_ups.items())),
            "false_positives": sorted(list(self.false_positives)),
        }
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=4)

    def export_to_txt(self):
        content = self.txt.toPlainText()
        if not content.strip():
            QMessageBox.warning(self, "Empty", "There are no lyrics to export!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Lyrics to Text File",
            "lyric_export.txt",
            "Text Files (*.txt);;All Files (*.*)",
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                QMessageBox.information(
                    self, "Success", f"Lyrics saved to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save file: {e}")

    def import_from_txt(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Lyrics File", "", "Text Files (*.txt);;All Files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.take_snapshot()
                self.txt.setPlainText(content)
                self.refresh_highlights()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not read file: {e}")

    def show_context_menu(self, event):
        tc = self.txt.cursorForPosition(event.pos())
        self.txt.setTextCursor(tc)

        if self.get_word_at_cursor():
            menu = QMenu(self)

            ignore_action = QAction("  Ignore (False Positive)  ", self)
            ignore_action.triggered.connect(self.add_to_false_pos)
            menu.addAction(ignore_action)

            add_action = QAction("  Add to Trip-Ups...  ", self)
            add_action.triggered.connect(self.add_to_trip_ups)
            menu.addAction(add_action)

            menu.exec(event.globalPos())

    def get_word_at_cursor(self):
        tc = self.txt.textCursor()
        tc.select(QTextCursor.SelectionType.LineUnderCursor)
        line_text = tc.selectedText()
        col = self.txt.textCursor().positionInBlock()

        match = next(
            (
                m
                for m in re.finditer(r"[\w/_']+", line_text)
                if m.start() <= col <= m.end()
            ),
            None,
        )
        return match.group() if match else None

    def add_to_false_pos(self):
        word = self.get_word_at_cursor()
        if word:
            clean = word.replace("/", "").replace("_", "").lower()
            self.false_positives.add(clean)
            self.save_config_to_disk()
            self.refresh_highlights()

    def add_to_trip_ups(self):
        word = self.get_word_at_cursor()
        if not word:
            return
        clean_display = word.replace("/", "").replace("_", "")
        dialog = WordInputDialog(
            self,
            title="New Trip-Up",
            text=f"How should '{clean_display}' be split?",
            initial_value=clean_display,
        )
        res = dialog.get_input()
        if res:
            clean_key = clean_display.lower()
            self.trip_ups[clean_key] = res.strip().lower()
            self.save_config_to_disk()
            self.refresh_highlights()
            self.auto_split()

    def open_editor(self):
        editor = ConfigEditor(self)
        editor.exec()

    def open_about(self):
        about = AboutDialog(self)
        about.exec()

    def take_snapshot(self, event=None):
        is_trigger = False
        if event is None:
            is_trigger = True
        elif hasattr(event, "text") and event.text() in ["/", "_"]:
            is_trigger = True
        elif hasattr(event, "key") and event.key() in [Qt.Key_Backspace, Qt.Key_Delete]:
            is_trigger = True

        if is_trigger:
            self.pre_keypress_snapshot = self.txt.toPlainText()
            self.history.append(self.pre_keypress_snapshot)

    def on_key_release(self, event):
        is_trigger = False
        if hasattr(event, "text") and event.text() in ["/", "_"]:
            is_trigger = True
        elif hasattr(event, "key") and event.key() in [Qt.Key_Backspace, Qt.Key_Delete]:
            is_trigger = True

        if is_trigger:
            self.live_sync_word()
        self.refresh_highlights()

    def live_sync_word(self):
        if not self.pre_keypress_snapshot:
            return

        scroll = self.txt.verticalScrollBar().value()
        cursor_pos = self.txt.textCursor().position()
        current_content = self.txt.toPlainText()

        tc = self.txt.textCursor()
        tc.select(QTextCursor.SelectionType.LineUnderCursor)
        full_line = tc.selectedText()
        col = self.txt.textCursor().positionInBlock()

        new_text, changed = calculate_live_sync(self.pre_keypress_snapshot, current_content, full_line, col)
        
        if changed:
            self.history.append(current_content)
            self.pre_keypress_snapshot = ""

            self.txt.setPlainText(new_text)

            new_tc = self.txt.textCursor()
            new_tc.setPosition(cursor_pos)
            self.txt.setTextCursor(new_tc)
            self.txt.verticalScrollBar().setValue(scroll)

    def refresh_highlights(self):
        self.txt.setExtraSelections([])
        if not self.highlight_var.isChecked() or not self.dic:
            return

        content = self.txt.toPlainText()
        selections = []

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#5c4000"))
        fmt.setForeground(QColor("white"))

        for m in re.finditer(r"(?<![/_])\b[\w']+\b(?![/_])", content):
            word, low = m.group(), m.group().lower()
            if (
                int(len(word)) <= int(self.highlight_threshold)
                and low not in self.trip_ups
            ):
                continue
            if low in self.false_positives:
                continue

            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            tc = self.txt.textCursor()
            tc.setPosition(m.start())
            tc.setPosition(m.end(), QTextCursor.MoveMode.KeepAnchor)
            sel.cursor = tc
            selections.append(sel)

        self.txt.setExtraSelections(selections)

    def auto_split(self):
        if not self.dic:
            return
            
        scroll = self.txt.verticalScrollBar().value()
        self.history.append(self.txt.toPlainText())
        content = self.txt.toPlainText()
        
        new_text = auto_split_text(content, self.dic, self.trip_ups)

        self.txt.setPlainText(new_text)
        self.txt.verticalScrollBar().setValue(scroll)
        self.refresh_highlights()

    def reset_copy_btn(self):
        self.copy_btn.setText("Copy Lyrics")
        self.copy_btn.setStyleSheet(
            "background-color: #1f538d; color: white; font-weight: bold; padding: 6px;"
        )

    def copy_to_clipboard(self):
        content = self.txt.toPlainText()
        QApplication.clipboard().setText(content)

        self.copy_btn.setText("Copied!")
        self.copy_btn.setStyleSheet(
            "background-color: #2c5d3f; color: white; font-weight: bold; padding: 6px;"
        )
        QTimer.singleShot(1000, lambda: self.reset_copy_btn())

    def sanitize_lyrics(self):
        self.take_snapshot(None)
        content = self.txt.toPlainText()
        
        final_text = sanitize_lyrics_text(content)
        
        self.txt.setPlainText(final_text)
        self.refresh_highlights()

    def undo(self, event=None):
        if self.history:
            scroll = self.txt.verticalScrollBar().value()
            self.txt.setPlainText(self.history.pop())
            self.txt.verticalScrollBar().setValue(scroll)
            self.refresh_highlights()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local Lyric Splitter Engine")
    parser.add_argument("--artist", type=str, help="Artist name", default="")
    parser.add_argument("--song", type=str, help="Song title", default="")
    parser.add_argument(
        "--audio", type=str, help="Absolute path to the audio file for KBP", default=""
    )
    parser.add_argument(
        "--out",
        type=str,
        help="Directory to save the exported TXT and KBP files",
        default="",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run fetch/split/save automatically and then close",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Run silently without showing the UI or message boxes",
    )
    parser.add_argument(
        "--edit",
        type=str,
        help="Absolute path to a .txt file to open on startup",
        default="",
    )
    args, unknown = parser.parse_known_args()

    if not args.edit and unknown:
        potential_file = unknown[0]
        if os.path.exists(potential_file):
            args.edit = potential_file

    app = QApplication(sys.argv)
    window = StreamlinedLyricApp(cli_args=args)

    if not args.silent:
        window.show()

    sys.exit(app.exec())
