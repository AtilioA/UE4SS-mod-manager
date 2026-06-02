## 2.0.0
- **Complete Architecture Rewrite**: Transitioned from a Python GUI to a modern, high-performance desktop application built with Rust and Tauri.
- **Enhanced Archive Support**: Native drag-and-drop support for ZIP, 7-Zip (`.7z`), and RAR (`.rar`) mod archive extraction.
- **Robust Mod Management**:
  - Automatic detection and support for nested folder installations.
  - Smart mod replacement and updates.
  - Secure mod uninstallation.
  - Improved mod activation logic with optimized fallback modes (`enabled.txt` vs. `mods.txt`).
- **Integrated Config Editor**: Introduced a line-preserving global UE4SS settings editor directly in the UI.
- **Polished UI & UX**:
  - Sleek modern interface with smooth toast notifications and modal transitions.
  - Interactive "Launch Game" feature.
  - Dynamic button states (e.g., auto-disabling "Save Changes" when not dirty).
  - Multi-platform design enhancements with robust Game Pass/Xbox support.

## 0.2.0
- Added search filter
- Added "reset" and "refresh" buttons
- Added warnings when writing to mods.txt and mods.json
- Added warning when trying to manage native UE4SS mods
- Misc bug fixes

## 0.1.0
- Initial version.