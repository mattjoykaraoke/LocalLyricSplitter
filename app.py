import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pyphen
import requests
from bs4 import BeautifulSoup
from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QPixmap,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

APP_VERSION = "2.1.0"

# --- NETWORK WORKER ---


class LyricFetchWorker(QThread):
    """Threaded worker to prevent UI freezing during network requests."""

    success = Signal(str)
    failure = Signal(str)

    def __init__(self, artist, title):
        super().__init__()
        self.artist = artist.strip()
        self.title = title.strip()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def run(self):
        try:
            # 1. Genius Search & Scrape
            lyrics = self.fetch_genius()
            if lyrics:
                self.success.emit(lyrics)
                return

            # 2. AZLyrics Backup
            lyrics = self.fetch_azlyrics()
            if lyrics:
                self.success.emit(lyrics)
                return

            # 3. LRCLIB Open API Backup (Highly reliable for popular songs)
            lyrics = self.fetch_lrclib_fallback()
            if lyrics:
                self.success.emit(lyrics)
                return

            self.failure.emit("Lyrics not found on Genius, AZLyrics, or LRCLIB.")
        except Exception as e:
            self.failure.emit(f"Connection error: {str(e)}")

    def fetch_genius(self):
        try:
            query = f"{self.artist} {self.title}".replace(" ", "%20")
            url = f"https://genius.com/api/search/multi?q={query}"
            response = requests.get(url, headers=self.headers, timeout=10)
            data = response.json()

            for section in data["response"]["sections"]:
                if section["type"] == "top_hit" and section["hits"]:
                    song_url = section["hits"][0]["result"]["url"]
                    page = requests.get(song_url, headers=self.headers, timeout=10)
                    soup = BeautifulSoup(page.text, "html.parser")

                    lyrics_divs = soup.select('div[class^="Lyrics__Container"]')
                    if lyrics_divs:
                        return "\n".join(
                            [d.get_text(separator="\n") for d in lyrics_divs]
                        )
            return None
        except Exception:
            return None

    def fetch_azlyrics(self):
        try:
            clean_artist = re.sub(r"[^a-z0-9]", "", self.artist.lower())
            clean_title = re.sub(r"[^a-z0-9]", "", self.title.lower())
            url = f"https://www.azlyrics.com/lyrics/{clean_artist}/{clean_title}.html"

            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            comment = soup.find(
                string=lambda text: (
                    "Usage of azlyrics.com content" in text if text else False
                )
            )
            if comment:
                return comment.find_next("div").get_text().strip()
            return None
        except Exception:
            return None

    def fetch_lrclib_fallback(self):
        """Replaces Google scrape with a robust, free open-source lyrics API."""
        try:
            query = f"{self.artist} {self.title}"
            url = f"https://lrclib.net/api/search?q={urllib.parse.quote(query)}"

            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    # Grab the plain lyrics from the first result
                    lyrics = data[0].get("plainLyrics")
                    if lyrics:
                        return lyrics
            return None
        except Exception:
            return None


# --- CORE APPLICATION ---


def get_config_path():
    """
    Priority logic:
    1. If NOT compiled (Dev mode): Use config.json in the script folder.
    2. If compiled (Installed mode): Use %APPDATA% ONLY.
    """
    is_frozen = getattr(sys, "frozen", False)

    if not is_frozen:
        local_config = Path(__file__).parent / "config.json"
        return str(local_config)

    # Added fallback empty string to satisfy linter type checking for os.getenv
    app_data_dir = Path(os.getenv("APPDATA", "")) / "LocalLyricSplitter"
    config_file = app_data_dir / "config.json"

    if not app_data_dir.exists():
        app_data_dir.mkdir(parents=True)

    if not config_file.exists():
        bundled_config = Path(getattr(sys, "_MEIPASS", "")) / "config.json"
        if bundled_config.exists():
            try:
                shutil.copy(bundled_config, config_file)
                return str(config_file)
            except Exception:
                pass

        default_config = {"trip_up_words": {"into": "in/to"}, "false_positives": []}
        with open(config_file, "w") as f:
            json.dump(default_config, f, indent=4)

    return str(config_file)


class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("About Local Lyric Splitter")
        self.setFixedSize(450, 520)
        self.app_path = parent.app_path

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        assets_path = os.path.join(self.app_path, "assets")
        image_path = os.path.join(assets_path, "about_logo.png")

        self.logo_label = QLabel()
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path).scaled(
                300,
                200,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_label.setPixmap(pixmap)
        else:
            self.logo_label.setText("[ about_logo.png not found ]")
            self.logo_label.setFixedSize(300, 200)
            self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.logo_label.setStyleSheet("background-color: #333; color: white;")

        layout.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignCenter)

        about_text = (
            f"Vibe Coded in 2026 by Matt Joy.\n\n"
            f"Version {APP_VERSION}\n"
            f"Built with PySide6 (LGPL)\n"
            f"See licenses folder for details."
        )
        text_label = QLabel(about_text)
        text_label.setFont(QFont("Arial", 11))
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_label)

        yt_link = QLabel(
            '<a href="https://www.youtube.com/@MattJoyKaraoke" style="color:#708090;">youtube.com/@MattJoyKaraoke</a>'
        )
        yt_link.setFont(QFont("Arial", 10))
        yt_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        yt_link.setOpenExternalLinks(True)
        layout.addWidget(yt_link)

        gh_link = QLabel(
            '<a href="https://github.com/mattjoykaraoke" style="color:#708090;">github.com/mattjoykaraoke</a>'
        )
        gh_link.setFont(QFont("Arial", 10))
        gh_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gh_link.setOpenExternalLinks(True)
        layout.addWidget(gh_link)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


class WordInputDialog(QDialog):
    def __init__(self, parent, title, text, initial_value=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 220)

        # Renamed from self.result to self.user_input to avoid Qt native method collision
        self.user_input = None

        layout = QVBoxLayout(self)

        label = QLabel(text)
        label.setFont(QFont("Arial", 12))
        layout.addWidget(label)

        self.entry = QLineEdit()
        self.entry.setText(initial_value)
        layout.addWidget(self.entry)
        self.entry.setFocus()

        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ok_btn = QPushButton("Ok")
        ok_btn.setFixedWidth(100)
        ok_btn.clicked.connect(self.submit)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def submit(self):
        self.user_input = self.entry.text()
        self.accept()

    def get_input(self):
        self.exec()
        return self.user_input


class ConfigEditor(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        # Renamed from self.parent to avoid colliding with QDialog's built-in parent() method
        self.main_app = parent
        self.setWindowTitle("Configuration Editor")
        self.resize(620, 600)

        layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<b>Trip-Up Words (word: split)</b>"))
        header_layout.addWidget(QLabel("<b>False Positives (ignore)</b>"))
        layout.addLayout(header_layout)

        lists_layout = QHBoxLayout()
        self.trip_up_list = QTextEdit()
        self.trip_up_list.setFont(QFont("Consolas", 11))

        self.false_pos_list = QTextEdit()
        self.false_pos_list.setFont(QFont("Consolas", 11))

        lists_layout.addWidget(self.trip_up_list)
        lists_layout.addWidget(self.false_pos_list)
        layout.addLayout(lists_layout)

        self.load_into_editor()

        btn_layout = QHBoxLayout()

        save_btn = QPushButton("Save && Apply")
        save_btn.setStyleSheet(
            "background-color: #2c5d3f; color: white; font-weight: bold;"
        )
        save_btn.clicked.connect(self.save_and_close)

        export_btn = QPushButton("Export Library")
        export_btn.setStyleSheet(
            "background-color: #1f538d; color: white; font-weight: bold;"
        )
        export_btn.clicked.connect(self.export_config)

        import_btn = QPushButton("Import/Merge")
        import_btn.setStyleSheet(
            "background-color: #444; color: white; font-weight: bold;"
        )
        import_btn.clicked.connect(self.import_config)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(export_btn)
        btn_layout.addWidget(import_btn)
        layout.addLayout(btn_layout)

    def load_into_editor(self):
        self.trip_up_list.clear()
        self.false_pos_list.clear()
        trip_str = "\n".join([f"{k}: {v}" for k, v in self.main_app.trip_ups.items()])
        self.trip_up_list.setPlainText(trip_str)
        false_str = "\n".join(sorted(list(self.main_app.false_positives)))
        self.false_pos_list.setPlainText(false_str)

    def export_config(self):
        source_path = self.main_app.config_path

        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Your Lyric Library",
            "LLS_My_Library.json",
            "JSON File (*.json)",
        )

        if dest_path:
            try:
                shutil.copy(source_path, dest_path)
                QMessageBox.information(
                    self, "Success", f"Library exported to:\n{dest_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Failed", f"Could not export file: {e}"
                )

    def import_config(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Library to Import", "", "JSON File (*.json)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                new_data = json.load(f)

            new_trips = new_data.get("trip_up_words", {})
            new_false = new_data.get("false_positives", [])

            merged_count = 0
            for k, v in new_trips.items():
                if k.lower() not in self.main_app.trip_ups:
                    self.main_app.trip_ups[k.lower()] = v.lower()
                    merged_count += 1

            for fp in new_false:
                if fp.lower() not in self.main_app.false_positives:
                    self.main_app.false_positives.add(fp.lower())
                    merged_count += 1

            self.main_app.save_config_to_disk()
            self.load_into_editor()
            QMessageBox.information(
                self,
                "Import Success",
                f"Merged {merged_count} new entries into your library!",
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to parse file: {e}")

    def save_and_close(self):
        new_trip_ups = {}
        for line in self.trip_up_list.toPlainText().split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                new_trip_ups[key.strip().lower()] = val.strip().lower()
        new_false_pos = [
            line.strip().lower()
            for line in self.false_pos_list.toPlainText().split("\n")
            if line.strip()
        ]

        self.main_app.trip_ups = new_trip_ups
        self.main_app.false_positives = set(new_false_pos)
        self.main_app.save_config_to_disk()
        self.main_app.refresh_highlights()
        self.accept()


class LyricTextEdit(QTextEdit):
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app

        # Enforce exact font via stylesheet to prevent formatting resets
        self.setStyleSheet("font-family: 'Consolas'; font-size: 14pt;")
        self.setFont(QFont("Consolas", 14))

        # Disable Rich Text parsing globally
        self.setAcceptRichText(False)

        # Enable drag and drop
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            # Only accept .txt files
            if (
                urls
                and urls[0].isLocalFile()
                and urls[0].toLocalFile().lower().endswith(".txt")
            ):
                event.acceptProposedAction()
                return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if (
                urls
                and urls[0].isLocalFile()
                and urls[0].toLocalFile().lower().endswith(".txt")
            ):
                event.acceptProposedAction()
                return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if (
                urls
                and urls[0].isLocalFile()
                and urls[0].toLocalFile().lower().endswith(".txt")
            ):
                file_path = urls[0].toLocalFile()
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Take snapshot for undo, set text, and refresh highlighting
                    self.parent_app.take_snapshot()
                    self.setPlainText(content)
                    self.parent_app.refresh_highlights()

                    event.acceptProposedAction()
                    return
                except Exception as e:
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.critical(
                        self, "Error", f"Could not read dragged file: {e}"
                    )
        super().dropEvent(event)

    def insertFromMimeData(self, source):
        # Guaranteed plain text intercept (Strips Genius's HTML layout instantly)
        if source.hasText():
            self.insertPlainText(source.text())

    def keyPressEvent(self, event: QKeyEvent):
        self.parent_app.take_snapshot(event)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        super().keyReleaseEvent(event)
        self.parent_app.on_key_release(event)

    def contextMenuEvent(self, event):
        self.parent_app.show_context_menu(event)


class StreamlinedLyricApp(QMainWindow):
    def __init__(self):
        super().__init__()

        if getattr(sys, "frozen", False):
            # Added getattr to satisfy the linter's strict checks for PyInstaller's dynamic properties
            self.app_path = str(getattr(sys, "_MEIPASS", ""))
            self.exe_dir = os.path.dirname(sys.executable)
        else:
            self.app_path = os.path.dirname(__file__)
            self.exe_dir = self.app_path

        self.config_path = get_config_path()

        # Type hints to tell the linter exactly what data lives in these variables
        self.trip_ups: dict[str, str] = {}
        self.false_positives: set[str] = set()

        self.load_config()

        self.dic = pyphen.Pyphen(lang="en_US")
        self.history = []
        self.pre_keypress_snapshot = ""

        self.setWindowTitle(f"Local Lyric Splitter v{APP_VERSION}")
        self.resize(1000, 800)

        # Updated to use FlagCDN identifier instead of text emojis
        self.lang_profiles = {
            "English": {"flag": "us", "pyphen": "en_US", "threshold": 5},
            "Spanish": {"flag": "mx", "pyphen": "es", "threshold": 6},
            "French": {"flag": "fr", "pyphen": "fr_FR", "threshold": 7},
            "German": {"flag": "de", "pyphen": "de_DE", "threshold": 10},
            "Russian": {"flag": "ru", "pyphen": "ru_RU", "threshold": 7},
        }
        self.current_lang_name = "English"

        # Explicit cast to int to satisfy linter comparison rules
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

        # --- NEW SEARCH UI INTEGRATED HERE ---
        self.artist_input = QLineEdit()
        self.artist_input.setPlaceholderText("Artist Name...")
        self.artist_input.setFixedWidth(200)

        self.song_input = QLineEdit()
        self.song_input.setPlaceholderText("Song Title...")
        self.song_input.setFixedWidth(250)

        self.fetch_btn = QPushButton("Fetch Lyrics")
        self.fetch_btn.setStyleSheet(
            "background-color: #1f538d; color: white; font-weight: bold; padding: 4px 10px;"
        )
        self.fetch_btn.clicked.connect(self.start_lyric_fetch)

        self.header_frame.addWidget(QLabel("<b>Fetch:</b>"))
        self.header_frame.addWidget(self.artist_input)
        self.header_frame.addWidget(self.song_input)
        self.header_frame.addWidget(self.fetch_btn)

        self.header_frame.addStretch()
        # -------------------------------------

        self.lang_menu = QComboBox()
        self.lang_menu.setIconSize(QSize(20, 15))

        for lang_name, profile in self.lang_profiles.items():
            icon = self.get_flag_icon(profile["flag"])
            self.lang_menu.addItem(icon, lang_name)

        self.lang_menu.currentTextChanged.connect(self.change_language)
        self.lang_menu.setMinimumWidth(150)
        self.header_frame.addWidget(self.lang_menu)
        self.main_layout.addLayout(self.header_frame)

        # Editor
        self.txt = LyricTextEdit(self)
        self.main_layout.addWidget(self.txt)

        # Setup native undo binding
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self.undo)

        self.control_bar = QHBoxLayout()

        self.highlight_var = QCheckBox("Highlighting")
        self.highlight_var.setChecked(True)
        self.highlight_var.stateChanged.connect(self.refresh_highlights)
        self.control_bar.addWidget(self.highlight_var)

        self.add_control_btn("Auto-Split", "#2c5d3f", self.auto_split)

        self.copy_btn = QPushButton("Copy Lyrics")
        self.copy_btn.setStyleSheet(
            "background-color: #1f538d; color: white; font-weight: bold; padding: 6px;"
        )
        self.copy_btn.setMinimumWidth(110)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        self.control_bar.addWidget(self.copy_btn)

        self.add_control_btn("Sanitize", "#721c24", self.sanitize_lyrics)
        self.add_control_btn("Config", "#444", self.open_editor)
        self.add_control_btn("About", "#444", self.open_about)

        self.control_bar.addStretch()

        self.add_control_btn("Undo", "#721c24", self.undo)

        self.main_layout.addLayout(self.control_bar)

    # --- NEW FETCH METHODS ---
    def start_lyric_fetch(self):
        artist = self.artist_input.text()
        song = self.song_input.text()
        if not artist or not song:
            QMessageBox.warning(
                self, "Input Required", "Please enter both Artist and Song Title."
            )
            return

        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Searching...")

        self.worker = LyricFetchWorker(artist, song)
        self.worker.success.connect(self.on_fetch_success)
        self.worker.failure.connect(self.on_fetch_error)
        self.worker.start()

    def on_fetch_success(self, lyrics):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch Lyrics")
        self.take_snapshot()
        self.txt.setPlainText(lyrics)
        self.sanitize_lyrics()  # Auto-sanitize triggers automatically
        self.refresh_highlights()

    def on_fetch_error(self, message):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch Lyrics")
        QMessageBox.warning(self, "Not Found", message)

    # -------------------------

    def get_flag_icon(self, country_code):
        config_dir = os.path.dirname(self.config_path)
        flags_dir = os.path.join(config_dir, "flags")
        os.makedirs(flags_dir, exist_ok=True)

        icon_path = os.path.join(flags_dir, f"{country_code}.png")
        if not os.path.exists(icon_path):
            try:
                url = f"https://flagcdn.com/w20/{country_code}.png"
                urllib.request.urlretrieve(url, icon_path)
            except Exception:
                return QIcon()
        return QIcon(icon_path)

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

            # Use isinstance to narrow the type from QCoreApplication to QApplication
            app_instance = QApplication.instance()
            if isinstance(app_instance, QApplication):
                app_instance.setWindowIcon(app_icon)

    def change_language(self, selected_name):
        profile = self.lang_profiles.get(selected_name)
        if profile:
            self.current_lang_name = selected_name
            self.dic = pyphen.Pyphen(lang=profile["pyphen"])
            # Cast threshold to int to prevent comparison errors
            self.highlight_threshold = int(profile["threshold"])
            self.refresh_highlights()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                try:
                    config = json.load(f)

                    # Force the items to strings to satisfy the linter's strict type checking
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
        if event is None or (hasattr(event, "text") and event.text() in ["/", "_"]):
            self.history.append(self.txt.toPlainText())

    def on_key_release(self, event):
        if hasattr(event, "text") and event.text() in ["/", "_"]:
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

        target = next(
            (
                m.group()
                for m in re.finditer(r"\S+", full_line)
                if m.start() <= col <= m.end()
            ),
            None,
        )
        if target and ("/" in target or "_" in target):
            base = re.sub(r"[/_]", "", target)
            pattern = re.compile(
                rf"(?<!\w){''.join([re.escape(c) + r'[/_]*' for c in base])[:-5]}(?!\w)",
                re.IGNORECASE,
            )
            if pattern.search(self.pre_keypress_snapshot):
                self.history.append(self.pre_keypress_snapshot)
                self.pre_keypress_snapshot = ""

                new_text = pattern.sub(target, current_content)
                self.txt.setPlainText(new_text)

                new_tc = self.txt.textCursor()
                new_tc.setPosition(cursor_pos)
                self.txt.setTextCursor(new_tc)
                self.txt.verticalScrollBar().setValue(scroll)

    def refresh_highlights(self):
        self.txt.setExtraSelections([])
        if not self.highlight_var.isChecked():
            return

        content = self.txt.toPlainText()
        selections = []

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#5c4000"))
        fmt.setForeground(QColor("white"))

        for m in re.finditer(r"(?<![/_])\b[\w']+\b(?![/_])", content):
            word, low = m.group(), m.group().lower()
            # Explicit cast of length check logic to avoid comparison mismatch warnings
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
        scroll = self.txt.verticalScrollBar().value()
        self.history.append(self.txt.toPlainText())
        content = self.txt.toPlainText()
        parts = re.split(r"([^a-zA-Z0-9'/_-]+)", content)
        processed = []
        for p in parts:
            low = p.lower()
            if low in self.trip_ups:
                res = self.trip_ups[low]
                processed.append(res.capitalize() if p[0].isupper() else res)
            elif (
                not p.strip() or not any(c.isalnum() for c in p) or "/" in p or "_" in p
            ):
                processed.append(p)
            elif "-" in p:
                sub_words = p.split("-")
                hyphenated_chunks = []
                for sub in sub_words:
                    sub_low = sub.lower()
                    if sub_low in self.trip_ups:
                        res = self.trip_ups[sub_low]
                        hyphenated_chunks.append(
                            res.capitalize() if sub and sub[0].isupper() else res
                        )
                    else:
                        hyphenated_chunks.append(self.dic.inserted(sub, hyphen="/"))
                processed.append("-/".join(hyphenated_chunks))
            else:
                processed.append(self.dic.inserted(p, hyphen="/"))

        self.txt.setPlainText("".join(processed))
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
        """Removes Genius metadata, ads, and structural tags while preserving stanza spacing."""
        self.take_snapshot(None)
        content = self.txt.toPlainText()
        lines = content.splitlines()

        # 1. Pre-pass: If we find an early bracket (e.g., [Verse 1]), wipe out the top block completely.
        first_bracket_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("["):
                first_bracket_idx = i
                break

        if first_bracket_idx > 0:
            header_text = "\n".join(lines[:first_bracket_idx]).lower()
            # Verify it's a metadata block before deleting
            if (
                "contributor" in header_text
                or "lyrics" in header_text
                or "read more" in header_text
            ):
                lines = lines[first_bracket_idx:]

        # 2. Line-by-Line cleanup
        cleaned_lines = []
        skip_count = 0
        skipping_blurb = False

        for line in lines:
            stripped = line.strip()

            # Handle dynamic blurb skipping (e.g., descriptions before the lyrics)
            if skipping_blurb:
                if (
                    stripped.lower() == "read more"
                    or stripped.startswith("[")
                    or stripped == ""
                ):
                    skipping_blurb = False
                    if stripped.lower() == "read more":
                        continue
                if skipping_blurb:
                    continue

            if skip_count > 0:
                skip_count -= 1
                continue

            # Triggers to start skipping lines
            if re.match(r"^\d+\s*Contributors?$", stripped, re.IGNORECASE):
                skipping_blurb = True
                continue

            if re.match(r"^See .* Live$", stripped, re.IGNORECASE):
                skip_count = 8
                continue

            if "You might also like" in stripped:
                skip_count = 6
                continue

            if stripped.lower() == "read more":
                continue

            # Catch stray "Song Title Lyrics" right at the top
            if stripped.lower().endswith("lyrics") and len(cleaned_lines) == 0:
                continue

            # Strip brackets and clean
            line_no_tags = re.sub(r"\[.*?\]", "", line).strip()

            # Prevent multiple stacked blank lines
            if line_no_tags == "":
                if cleaned_lines and cleaned_lines[-1] != "":
                    cleaned_lines.append("")
            else:
                cleaned_lines.append(line_no_tags)

        final_text = "\n".join(cleaned_lines).strip()
        self.txt.setPlainText(final_text)
        self.refresh_highlights()

    def undo(self, event=None):
        if self.history:
            scroll = self.txt.verticalScrollBar().value()
            self.txt.setPlainText(self.history.pop())
            self.txt.verticalScrollBar().setValue(scroll)
            self.refresh_highlights()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StreamlinedLyricApp()
    window.show()
    sys.exit(app.exec())
