import json
import os
import re
import shutil
import sys
import webbrowser
from pathlib import Path
from tkinter import Menu, filedialog, messagebox

import customtkinter as ctk
import pyphen
from PIL import Image

APP_VERSION = "1.2.0"


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

    app_data_dir = Path(os.getenv("APPDATA")) / "LocalLyricSplitter"
    config_file = app_data_dir / "config.json"

    if not app_data_dir.exists():
        app_data_dir.mkdir(parents=True)

    if not config_file.exists():
        bundled_config = Path(sys._MEIPASS) / "config.json"
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


class AboutDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("About Local Lyric Splitter")
        self.geometry("450x520")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grid_columnconfigure(0, weight=1)

        display_size = (300, 200)
        assets_path = os.path.join(parent.app_path, "assets")
        image_path = os.path.join(assets_path, "about_logo.png")

        if os.path.exists(image_path):
            try:
                pil_image = Image.open(image_path)
                self.logo_image = ctk.CTkImage(
                    light_image=pil_image, dark_image=pil_image, size=display_size
                )
            except Exception:
                self.logo_image = None
        else:
            self.logo_image = None

        if self.logo_image:
            ctk.CTkLabel(self, image=self.logo_image, text="").pack(pady=(20, 10))
        else:
            ctk.CTkLabel(
                self,
                text="[ about_logo.png not found ]",
                width=300,
                height=200,
                fg_color="#333",
            ).pack(pady=(20, 10))

        about_text = (
            f"Vibe Coded in 2026 by Matt Joy.\n\n"
            f"Version {APP_VERSION}\n"
            f"Built with CustomTkinter (MIT License)\n"
            f"See licenses folder for details."
        )
        ctk.CTkLabel(self, text=about_text, font=("Arial", 13), justify="center").pack(
            pady=(5, 5)
        )

        yt = ctk.CTkLabel(
            self,
            text="youtube.com/@MattJoyKaraoke",
            font=("Arial", 12, "underline"),
            text_color="#708090",
            cursor="hand2",
        )
        yt.pack(pady=2)
        yt.bind(
            "<Button-1>",
            lambda e: webbrowser.open("https://www.youtube.com/@MattJoyKaraoke"),
        )

        gh = ctk.CTkLabel(
            self,
            text="github.com/mattjoykaraoke",
            font=("Arial", 12, "underline"),
            text_color="#708090",
            cursor="hand2",
        )
        gh.pack(pady=2)
        gh.bind(
            "<Button-1>", lambda e: webbrowser.open("https://github.com/mattjoykaraoke")
        )

        ctk.CTkButton(self, text="Close", width=120, command=self.destroy).pack(
            pady=(20, 15)
        )


class WordInputDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, text, initial_value=""):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x220")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.result = None

        ctk.CTkLabel(self, text=text, font=("Arial", 14)).pack(pady=(25, 10))
        self.entry = ctk.CTkEntry(self, width=300)
        self.entry.pack(pady=10)
        self.entry.insert(0, initial_value)
        self.entry.focus_set()

        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=20)

        ctk.CTkButton(self.btn_frame, text="Ok", width=100, command=self.submit).pack(
            side="left", padx=10
        )
        ctk.CTkButton(
            self.btn_frame, text="Cancel", width=100, command=self.destroy
        ).pack(side="left", padx=10)
        self.bind("<Return>", lambda e: self.submit())

    def submit(self):
        self.result = self.entry.get()
        self.destroy()

    def get_input(self):
        self.master.wait_window(self)
        return self.result


class ConfigEditor(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Configuration Editor")
        self.geometry("620x600")
        self.attributes("-topmost", True)
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text="Trip-Up Words (word: split)", font=("Arial", 14, "bold")
        ).grid(row=0, column=0, pady=10)
        ctk.CTkLabel(
            self, text="False Positives (ignore)", font=("Arial", 14, "bold")
        ).grid(row=0, column=1, pady=10)

        self.trip_up_list = ctk.CTkTextbox(self, width=250, font=("Consolas", 12))
        self.trip_up_list.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.false_pos_list = ctk.CTkTextbox(self, width=250, font=("Consolas", 12))
        self.false_pos_list.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

        self.load_into_editor()

        # Bottom Button Row
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=2, column=0, columnspan=2, pady=20)

        ctk.CTkButton(
            self.btn_frame,
            text="Save & Apply",
            command=self.save_and_close,
            fg_color="#2c5d3f",
            width=130,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            self.btn_frame,
            text="Export Library",
            command=self.export_config,
            fg_color="#1f538d",
            width=130,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            self.btn_frame,
            text="Import/Merge",
            command=self.import_config,
            fg_color="#444",
            width=130,
        ).pack(side="left", padx=5)

    def load_into_editor(self):
        self.trip_up_list.delete("1.0", "end")
        self.false_pos_list.delete("1.0", "end")
        trip_str = "\n".join([f"{k}: {v}" for k, v in self.parent.trip_ups.items()])
        self.trip_up_list.insert("1.0", trip_str)
        false_str = "\n".join(sorted(list(self.parent.false_positives)))
        self.false_pos_list.insert("1.0", false_str)

    def export_config(self):
        source_path = self.parent.config_path
        dest_path = filedialog.asksaveasfilename(
            title="Export Your Lyric Library",
            initialfile="LLS_My_Library.json",
            filetypes=[("JSON File", "*.json")],
            defaultextension=".json",
        )
        if dest_path:
            try:
                shutil.copy(source_path, dest_path)
                messagebox.showinfo("Success", f"Library exported to:\n{dest_path}")
            except Exception as e:
                messagebox.showerror("Export Failed", f"Could not export file: {e}")

    def import_config(self):
        file_path = filedialog.askopenfilename(
            title="Select Library to Import", filetypes=[("JSON File", "*.json")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "r") as f:
                new_data = json.load(f)

            # Merge logic: Add new, don't overwrite user's custom existing ones
            new_trips = new_data.get("trip_up_words", {})
            new_false = new_data.get("false_positives", [])

            merged_count = 0
            for k, v in new_trips.items():
                if k.lower() not in self.parent.trip_ups:
                    self.parent.trip_ups[k.lower()] = v.lower()
                    merged_count += 1

            for fp in new_false:
                if fp.lower() not in self.parent.false_positives:
                    self.parent.false_positives.add(fp.lower())
                    merged_count += 1

            self.parent.save_config_to_disk()
            self.load_into_editor()  # Refresh view
            messagebox.showinfo(
                "Import Success",
                f"Merged {merged_count} new entries into your library!",
            )
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to parse file: {e}")

    def save_and_close(self):
        new_trip_ups = {}
        for line in self.trip_up_list.get("1.0", "end-1c").split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                new_trip_ups[key.strip().lower()] = val.strip().lower()
        new_false_pos = [
            line.strip().lower()
            for line in self.false_pos_list.get("1.0", "end-1c").split("\n")
            if line.strip()
        ]

        self.parent.trip_ups = new_trip_ups
        self.parent.false_positives = set(new_false_pos)
        self.parent.save_config_to_disk()
        self.parent.refresh_highlights()
        self.destroy()


class StreamlinedLyricApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        if getattr(sys, "frozen", False):
            self.app_path = sys._MEIPASS
            self.exe_dir = os.path.dirname(sys.executable)
        else:
            self.app_path = os.path.dirname(__file__)
            self.exe_dir = self.app_path

        self.config_path = get_config_path()
        self.load_config()

        self.dic = pyphen.Pyphen(lang="en_US")
        self.history = []
        self.pre_keypress_snapshot = ""

        self.title(f"Local Lyric Splitter v{APP_VERSION}")
        self.geometry("1000x800")
        ctk.set_appearance_mode("dark")

        # Define the rules for each language profile
        self.lang_profiles = {
            " [EN] English": {"pyphen": "en_US", "threshold": 5},
            " [ES] Spanish": {"pyphen": "es", "threshold": 6},
            " [FR] French": {"pyphen": "fr_FR", "threshold": 7},
            " [DE] German": {"pyphen": "de_DE", "threshold": 10},
            " [RU] Russian": {"pyphen": "ru_RU", "threshold": 7},
        }
        self.current_lang_name = " [EN] English"
        # This dynamically sets it to based on the language entry in your dict
        self.highlight_threshold = self.lang_profiles[self.current_lang_name][
            "threshold"
        ]

        # Header frame for the top-right dropdown
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(10, 0))

        # Language selection
        self.lang_options = list(self.lang_profiles.keys())

        self.lang_menu = ctk.CTkOptionMenu(
            self.header_frame,
            values=self.lang_options,
            command=self.change_language,
            width=180,
            font=("Segoe UI", 14),
        )
        self.lang_menu.pack(side="right")

        # This must be on its own line AFTER the menu is created
        self.lang_menu.set(self.current_lang_name)

        # Build the textbox
        self.txt = ctk.CTkTextbox(self, font=("Consolas", 18), undo=False)
        self.txt.pack(fill="both", expand=True, padx=20, pady=(20, 10))
        self.txt.tag_config("missed", background="#5c4000", foreground="white")

        # Right click context menu
        self.context_menu = Menu(
            self,
            tearoff=0,
            bg="#2b2b2b",
            fg="#e0e0e0",
            font=("Segoe UI", 10),
            activebackground="#1f538d",
            activeforeground="white",
        )
        self.context_menu.add_command(
            label="  Ignore (False Positive)  ", command=self.add_to_false_pos
        )
        self.context_menu.add_command(
            label="  Add to Trip-Ups...  ", command=self.add_to_trip_ups
        )

        self.txt.bind("<KeyPress>", self.take_snapshot)
        self.txt.bind("<KeyRelease>", self.on_key_release)
        self.txt.bind("<Button-3>", self.show_context_menu)
        self.bind("<Control-z>", self.undo)
        self.bind("<Control-Z>", self.undo)

        self.control_bar = ctk.CTkFrame(self)
        self.control_bar.pack(fill="x", padx=20, pady=10)
        self.highlight_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self.control_bar,
            text="Highlighting",
            variable=self.highlight_var,
            command=self.refresh_highlights,
        ).pack(side="left", padx=10)

        btn_w = 110
        ctk.CTkButton(
            self.control_bar,
            text="Auto-Split",
            command=self.auto_split,
            fg_color="#2c5d3f",
            width=btn_w,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            self.control_bar,
            text="Copy Lyrics",
            command=self.copy_to_clipboard,
            fg_color="#1f538d",
            width=btn_w,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            self.control_bar,
            text="Sanitize",
            command=self.sanitize_lyrics,
            fg_color="#721c24",  # A different color to show it's a "destructive" action
            width=btn_w,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            self.control_bar,
            text="Config",
            command=self.open_editor,
            fg_color="#444",
            width=btn_w,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            self.control_bar,
            text="About",
            command=self.open_about,
            fg_color="#444",
            width=btn_w,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            self.control_bar,
            text="Undo",
            command=self.undo,
            fg_color="#721c24",
            width=btn_w,
        ).pack(side="right", padx=10)

    def change_language(self, selected_name):
        profile = self.lang_profiles.get(selected_name)
        if profile:
            self.current_lang_name = selected_name
            self.dic = pyphen.Pyphen(lang=profile["pyphen"])
            self.highlight_threshold = profile["threshold"]
            self.refresh_highlights()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                try:
                    config = json.load(f)
                    self.trip_ups = dict(
                        sorted(config.get("trip_up_words", {}).items())
                    )
                    self.false_positives = set(config.get("false_positives", []))
                except json.JSONDecodeError:
                    self.trip_ups, self.false_positives = {}, set()
        else:
            self.trip_ups, self.false_positives = {}, set()

    def save_config_to_disk(self):
        data = {
            "trip_up_words": dict(sorted(self.trip_ups.items())),
            "false_positives": sorted(list(self.false_positives)),
        }
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=4)

    def show_context_menu(self, event):
        self.txt.mark_set("insert", self.txt.index(f"@{event.x},{event.y}"))
        if self.get_word_at_cursor():
            self.context_menu.post(event.x_root, event.y_root)

    def get_word_at_cursor(self):
        cursor_pos = self.txt.index("insert")
        line_text = self.txt.get(f"{cursor_pos} linestart", f"{cursor_pos} lineend")
        col = int(cursor_pos.split(".")[1])
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

        # Clean the word BEFORE showing the dialog so it looks right
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
        ConfigEditor(self)

    def open_about(self):
        AboutDialog(self)

    def take_snapshot(self, event=None):
        # If event is None (from a button), we ALWAYS take a snapshot.
        # If event is a keypress, we only take it for / or _
        if event is None or (event.char in ["/", "_"]):
            self.history.append(self.txt.get("1.0", "end-1c"))

    def on_key_release(self, event):
        if event.char in ["/", "_"]:
            self.live_sync_word()
        self.refresh_highlights()

    def live_sync_word(self):
        if not self.pre_keypress_snapshot:
            return
        scroll, cursor = self.txt.yview()[0], self.txt.index("insert")
        current_content = self.txt.get("1.0", "end-1c")
        full_line = self.txt.get(f"{cursor} linestart", f"{cursor} lineend")
        col = int(cursor.split(".")[1])
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
                self.txt.delete("1.0", "end")
                self.txt.insert("1.0", pattern.sub(target, current_content))
                self.txt.mark_set("insert", cursor)
                self.txt.yview_moveto(scroll)

    def refresh_highlights(self):
        self.txt.tag_remove("missed", "1.0", "end")
        if not self.highlight_var.get():
            return
        content = self.txt.get("1.0", "end-1c")
        for m in re.finditer(r"(?<![/_])\b[\w']+\b(?![/_])", content):
            word, low = m.group(), m.group().lower()
            if len(word) <= self.highlight_threshold and low not in self.trip_ups:
                continue
            if low in self.false_positives:
                continue
            start_idx, end_idx = f"1.0 + {m.start()} chars", f"1.0 + {m.end()} chars"
            self.txt.tag_add("missed", start_idx, end_idx)

    def auto_split(self):
        scroll = self.txt.yview()[0]
        self.history.append(self.txt.get("1.0", "end-1c"))
        content = self.txt.get("1.0", "end-1c")

        parts = re.split(r"([^a-zA-Z0-9'/_-]+)", content)
        processed = []

        for p in parts:
            low = p.lower()

            # 1. Check if the ENTIRE chunk is a Trip-Up (e.g., if you added "self-starter")
            if low in self.trip_ups:
                res = self.trip_ups[low]
                processed.append(res.capitalize() if p[0].isupper() else res)

            # 2. Skip whitespace, punctuation, or words that already have slashes/underscores
            elif (
                not p.strip() or not any(c.isalnum() for c in p) or "/" in p or "_" in p
            ):
                processed.append(p)

            # 3. Handle Hyphenated words safely
            elif "-" in p:
                sub_words = p.split("-")
                hyphenated_chunks = []

                for sub in sub_words:
                    sub_low = sub.lower()

                    # THE FIX: Check the dictionary for the sub-word FIRST
                    if sub_low in self.trip_ups:
                        res = self.trip_ups[sub_low]
                        hyphenated_chunks.append(
                            res.capitalize() if sub and sub[0].isupper() else res
                        )
                    else:
                        # Fallback to Pyphen
                        hyphenated_chunks.append(self.dic.inserted(sub, hyphen="/"))

                processed.append("-/".join(hyphenated_chunks))

            # 4. Standard Pyphen Auto-Split
            else:
                processed.append(self.dic.inserted(p, hyphen="/"))

        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "".join(processed))
        self.txt.yview_moveto(scroll)
        self.refresh_highlights()

    def copy_to_clipboard(self):
        content = self.txt.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        current_btn = [
            child
            for child in self.control_bar.winfo_children()
            if isinstance(child, ctk.CTkButton) and child.cget("text") == "Copy Lyrics"
        ]
        if current_btn:
            btn = current_btn[0]
            btn.configure(text="Copied!", fg_color="#2c5d3f")
            self.after(
                1000, lambda: btn.configure(text="Copy Lyrics", fg_color="#1f538d")
            )

    def sanitize_lyrics(self):
        """Removes Genius metadata, ads, and structural tags while preserving stanza spacing."""
        self.take_snapshot(None)

        content = self.txt.get("1.0", "end-1c")
        lines = content.splitlines()
        cleaned_lines = []
        skip_count = 0

        for i, line in enumerate(lines):
            stripped = line.strip()

            # 1. Skip garbage blocks
            if skip_count > 0:
                skip_count -= 1
                continue

            # 2. Identify 9-line "See [Artist] Live" ad
            if re.match(r"^See .* Live$", stripped):
                skip_count = 8
                continue

            # 3. Identify 7-line "You might also like" ad
            if "You might also like" in stripped:
                skip_count = 6
                continue

            # 4. Remove [Square Bracket] tags
            # We replace the tag with an empty string.
            line_no_tags = re.sub(r"\[.*?\]", "", line).strip()

            # 5. Spacing Logic
            if line_no_tags == "":
                # Only add a blank line if the previous line wasn't already blank
                if cleaned_lines and cleaned_lines[-1] != "":
                    cleaned_lines.append("")
            else:
                cleaned_lines.append(line_no_tags)

        # Final cleanup: Remove trailing/leading blank lines if they exist
        final_text = "\n".join(cleaned_lines).strip()

        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", final_text)
        self.refresh_highlights()

    def undo(self, event=None):
        if self.history:
            scroll = self.txt.yview()[0]
            self.txt.delete("1.0", "end")
            self.txt.insert("1.0", self.history.pop())
            self.txt.yview_moveto(scroll)
            self.refresh_highlights()
        return "break"


if __name__ == "__main__":
    app = StreamlinedLyricApp()
    app.mainloop()
