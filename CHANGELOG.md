# Changelog

All notable changes to Local Lyric Splitter will be documented in this file.

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
