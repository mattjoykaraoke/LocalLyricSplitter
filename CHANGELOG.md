# Changelog

All notable changes to Local Lyric Splitter will be documented in this file.

## [2.3.1] - 2026-04-28

### Fixed
**Windows Path Format:** The issue with the path format on windows has been resolved.

## [2.3.0] - 2026-04-25

### Added
**Modularization:** The code is now broken into smaller, more manageable files.

## [2.2.2] - 2026-04-11

### Added
**Export to .kbp:** You can now use the `file` menu to export to `.kbp` just select the audio file you're using and it will automatically put it together.

## [2.2.1] - 2026-04-11

### Added
**CLI:** You can pass commands to the `.exe` such as:
"--edit", path
**Dictionary Update:** Dictionaries will be updated with each release and when they become availble. Download the latest dictonary directly and merge within the app or update the program and merge with the dictionary in the directory (may be different depending on your install location): `C:\Program Files (x86)\Local Lyric Splitter\_internal\config.json`

## [2.2.0] - 2026-04-08

### Added
**CLI:** You can pass commands to the `.exe` such as:
"--artist", artist, 
"--song", song, 
"--audio", audio_path, 
"--out", export_dir,
"--silent"

### Changed
**Sanitize Function:** Now includes changing apostrophes to a standard `'` mark. I suggest running sanitize before doing anything else to make life easier and I moved the button to suggest this, as well.

## [2.1.0] - 2026-04-08

### Added
**Lyrics Fetching:** Lyrics can be automatically pulled from Genius, AZLyrics, or Google Search. When lyrics are pulled, the sanitizer runs automatically, as well. This is intentional for future automated workflows.

## [2.0.0] - 2026-04-07

### Added
**Complete UI Redesign:** Using PySide6 makes more sense and works better with high DPI screens and looks a lot more modern. Flags are now used for the language drop down, as well.
**Load and Save .txt files:** You can save your work or load up a lyrics `.txt` file from the file menu. You can also drag and drop anywhere in the app.

## [1.2.1] - 2026-04-07

### Fixed
**Window Management:** Avoids changing the config dialog while awaiting a merge or export to avoid a race condition.

## [1.2.0] - 2026-04-07

### Added
**Ad and Tag Removal:** Specific repetetive phrases like "See...Live" (9 lines) and "You might also like" (7 lines) patterns from Genius are removed entirely when you click `Sanitize`. `[Verse]`, `[Chorus]`, etc. are also removed.

**Spacing Protection:** `Sanitize` leaves exactly one blank line between stanzas, even if the source text had messy double-spacing or no spacing at all (if there were `[Tags]`).

**History Preservation:** The `Undo` button acts as a safety net if a "Sanitize" goes wrong.

## [1.1.0] - 2026-04-07

### Added
- **Multiple Languages:** English (default), Spanish, French, German, and Russian are all natively supported in `Pyphen` so you can now use the drop down menu to select them.

## [1.0.3] - 2026-04-07

### Fixed
- **Improved Regex Logic:** Similar issue fixed to previous.

## [1.0.2] - 2026-04-07

### Fixed
- **Improved Hyphenation Logic:** The new logic splits hyphened words into chunks and reconnects them with "-/" so the internal dictionary logic does not add double slashes anymore.

## [1.0.1] - 2026-04-07

### Added
- **Library Exporter:** Added a one-click Export Library button to the Config Editor, allowing users to save their custom dictionary as a shareable `.json` file.
- **Smart Library Merge:** Added an Import/Merge feature with additive logic. It allows users to import shared libraries without overwriting their own custom splits or "Ignore" lists.
- **Auto-Hyphenation:** Enhanced the `auto_split` engine to automatically detect hyphens and insert a slash immediately after them (e.g., `happy-place` ➡️ `happy-/place`).

### Fixed
- **Permission-Proof Config Path:** Refactored `get_config_path` to use Windows %APPDATA% for installed versions. This resolves "Access Denied" errors when saving Trip-Ups in `C:\Program Files`.
- **Environment Awareness:** Implemented a "Development Mode" check (sys.frozen) so the app automatically uses the local config.json while you're coding but switches to a writable user profile once installed.

## [1.0.0] - 2026-04-06

### Added
- **Initial Public Release:** See README for details.
