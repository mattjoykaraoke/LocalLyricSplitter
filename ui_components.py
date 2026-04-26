import os
import json
import shutil
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QFont,
    QPixmap,
    QKeyEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

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

        from config import APP_VERSION
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
