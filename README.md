# UE4SS Mod Manager

A desktop application for managing [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) mods in Unreal Engine games.

The current app is built with **Tauri v2**, using a Rust backend and a Vite-powered web UI. It is designed for users who want a simple way to install, enable, disable, configure, and remove UE4SS mods without manually editing `enabled.txt`, `mods.json`, `mods.txt`, `config.lua`, or `UE4SS-settings.ini`.

The legacy Python implementation is still present in the repository, but the recommended application path is the Tauri/Rust version.

## What It Does

UE4SS normally loads mods from a `UE4SS/Mods` folder. This manager scans that folder, detects valid UE4SS Lua and native mods, and lets you control them from one UI.

The app can:

- Detect a nearby `UE4SS/Mods` folder automatically when possible.
- Let you manually select the correct `UE4SS/Mods` folder when auto-detection fails.
- List valid mod folders sorted by name.
- Show whether a mod is enabled or disabled.
- Enable or disable individual mods.
- Toggle all visible mods at once.
- Hide or show known native UE4SS helper mods.
- Search mods by folder name or script/DLL file name.
- Install mods by dragging in a folder or supported archive.
- Install nested mod packages when the archive/folder contains wrapper directories.
- Delete installed mods from the managed `Mods` directory.
- Save mod state using one or more UE4SS-compatible strategies.
- Edit simple `scripts/config.lua` values for individual mods.
- Edit global `UE4SS-settings.ini` values grouped by INI section.
- Open the active Mods folder in the system file manager.
- Try to find and launch the game executable from nearby game folders.

## Supported Mod Layouts

A valid mod folder must contain one of these structures:

```text
ExampleMod/
└── scripts/
    └── main.lua
```

or:

```text
ExampleNativeMod/
└── dlls/
    └── main.dll
```

The manager also accepts folders or archives that wrap the real mod folder in a pure nested structure, for example:

```text
DownloadedPackage/
└── SomeGame/
    └── Binaries/
        └── Win64/
            └── ue4ss/
                └── Mods/
                    └── ExampleMod/
                        └── scripts/
                            └── main.lua
```

Wrapper folders are only unwrapped when each parent level contains exactly one child directory and no extra files. This avoids ambiguous or unsafe installs.

## Supported Archive Formats

Drag-and-drop installation supports:

- `.zip`
- `.7z`
- `.rar`
- regular folders

Unsupported single files such as `.txt`, `.exe`, `.png`, `.jpg`, `.pdf`, `.mp3`, `.mp4`, `.tar`, `.gz`, `.json`, `.dll`, and `.lua` are blocked by the frontend before they are sent to the backend.

## Save Strategies

UE4SS installations and mods do not always use the same enable/disable format. This manager can write multiple formats at the same time.

### `enabled.txt`

Creates or removes an empty `enabled.txt` file inside each mod folder.

```text
ExampleMod/
├── enabled.txt
└── scripts/
    └── main.lua
```

This is the default save strategy.

### `mods.json`

Writes a central JSON list of enabled mods:

```json
[
  {
    "mod_name": "ExampleMod",
    "mod_enabled": true
  }
]
```

### `mods.txt`

Writes a central text list of enabled mods:

```text
ExampleMod : 1
AnotherMod : 1
```

You can enable any combination of these strategies from the footer of the app.

## Configuration Editing

### Per-Mod `config.lua`

If a mod has `scripts/config.lua`, the UI shows a **Configure** button.

The parser supports simple top-level Lua table values:

- booleans: `true`, `false`
- numbers: `95`, `95.0`, `1e3`
- strings: `"text"` or `'text'`
- `nil`

Unsupported expressions, nested tables, and computed values are ignored instead of rewritten.

Example supported file:

```lua
return {
    Enabled = true,
    TargetFOV = 100,
    Name = "Example",
}
```

### Global `UE4SS-settings.ini`

The **UE4SS Settings** button opens the global `UE4SS-settings.ini` file when it is found next to the `Mods` folder:

```text
UE4SS/
├── UE4SS-settings.ini
└── Mods/
```

The INI editor preserves sections, comments, inline comments, and spacing as much as possible while updating changed values.

## Installation

### Option 1: Download a Pre-Built Release

This is the easiest path for normal users.

1. Download the latest release from the [Nexus page](https://www.nexusmods.com/subnautica2/mods/34), or from the project release page if one is provided.
2. Locate your game's UE4SS folder.
3. Put the executable somewhere convenient. Recommended locations:
   - directly inside the game folder
   - inside `UE4SS/`
   - inside `UE4SS/Mods/`
4. Start the executable.
5. If the app does not detect the folder automatically, click **Select Mods Directory**.
6. Select the actual `UE4SS/Mods` folder, not the game root and not a single mod folder.

Example Windows path:

```text
C:\Program Files (x86)\Steam\steamapps\common\GameName\Binaries\Win64\ue4ss\Mods
```

Example Linux/Proton path:

```text
/home/you/.steam/steam/steamapps/common/GameName/Binaries/Win64/ue4ss/Mods
```

After the folder is selected, the app remembers it in the platform config directory:

- Windows: `%APPDATA%\UE4SS Mod Manager\manager_config.json`
- macOS: `~/Library/Application Support/UE4SS Mod Manager/manager_config.json`
- Linux: `$XDG_CONFIG_HOME/UE4SS Mod Manager/manager_config.json` or `~/.config/UE4SS Mod Manager/manager_config.json`

### Option 2: Build from Source with Tauri

This is the recommended development and release build path.

The app uses:

- Rust for the backend
- Tauri v2 for the desktop shell
- Node.js/Vite for the frontend

#### Required Tools

| Tool | Recommended Version | Purpose |
|------|---------------------|---------|
| Node.js | 18 or newer | Installs frontend and Tauri CLI dependencies |
| npm | bundled with Node.js | Runs project scripts |
| Rust | stable | Builds the Tauri backend |
| Git | latest stable | Clones the repository |
| WebView runtime | platform-specific | Renders the Tauri UI |

Tauri's official prerequisite page is useful when setting up a new machine: <https://v2.tauri.app/start/prerequisites/>

#### Windows Build Setup

1. Install [Node.js](https://nodejs.org/).
2. Install [Rust](https://rustup.rs/).
3. During Rust setup, install the MSVC build tools when prompted.
4. If needed, install Visual Studio Build Tools manually:
   - Workload: **Desktop development with C++**
   - Windows SDK
   - MSVC C++ build tools
5. WebView2 is usually already installed on Windows 10/11. If not, install the [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/).

Build commands:

```powershell
git clone https://github.com/your-username/UE4SS-mod-manager.git
cd UE4SS-mod-manager
npm install
npm run tauri build
```

Output is created under:

```text
src-tauri/target/release/
src-tauri/target/release/bundle/
```

Common Windows artifacts:

```text
src-tauri/target/release/ue4ss-modmanager.exe
src-tauri/target/release/bundle/msi/
src-tauri/target/release/bundle/nsis/
```

#### Linux Build Setup

Install Node.js, Rust, Git, and the Tauri Linux system dependencies.

Ubuntu/Debian example:

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  curl \
  wget \
  file \
  libssl-dev \
  libdbus-1-dev \
  libgtk-3-dev \
  libayatana-appindicator3-dev \
  librsvg2-dev \
  libwebkit2gtk-4.1-dev \
  pkg-config
```

Fedora example:

```bash
sudo dnf install -y \
  gcc \
  gcc-c++ \
  make \
  curl \
  wget \
  file \
  openssl-devel \
  dbus-devel \
  gtk3-devel \
  libappindicator-gtk3-devel \
  librsvg2-devel \
  webkit2gtk4.1-devel \
  pkgconf-pkg-config
```

Arch example:

```bash
sudo pacman -S --needed \
  base-devel \
  curl \
  wget \
  file \
  openssl \
  dbus \
  gtk3 \
  libayatana-appindicator \
  librsvg \
  webkit2gtk-4.1 \
  pkgconf
```

Then build:

```bash
git clone https://github.com/your-username/UE4SS-mod-manager.git
cd UE4SS-mod-manager
npm install
npm run tauri:linux:build
```

The npm Tauri wrapper sets `CARGO_TARGET_DIR` to `~/.cache/ue4ss-mod-manager/target` by default when it detects WSL building from a Windows-mounted path such as `/mnt/c/...` or `/mnt/e/...`. This avoids `Operation not permitted` errors from Cargo build scripts writing generated files under `src-tauri/target`.

Linux output is created under:

```text
~/.cache/ue4ss-mod-manager/target/release/
~/.cache/ue4ss-mod-manager/target/release/bundle/
```

To use a different Linux build output directory, set `CARGO_TARGET_DIR` before running the script.

Depending on your distribution and installed bundling tools, Tauri may create AppImage, deb, rpm, or raw binary outputs.

#### macOS Build Setup

1. Install Xcode Command Line Tools:

   ```bash
   xcode-select --install
   ```

2. Install Node.js.
3. Install Rust.
4. Build:

   ```bash
   git clone https://github.com/your-username/UE4SS-mod-manager.git
   cd UE4SS-mod-manager
   npm install
   npm run tauri build
   ```

macOS bundles are created under:

```text
src-tauri/target/release/bundle/
```

### Development Mode

Use development mode when changing the UI or backend:

```bash
npm install
npm run tauri dev
```

This starts the Vite dev server and opens the Tauri window. Frontend changes reload quickly. Rust backend changes usually trigger a rebuild.

You can also run only the frontend build:

```bash
npm run build
```

And only check the Rust backend:

```bash
cd src-tauri
cargo check
```

Run Rust tests:

```bash
cd src-tauri
cargo test
```

### Option 3: Build the Legacy Python Version

The original Python version is still available for reference and compatibility.

#### Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

#### Setup

```bash
uv sync --dev
```

Run tests:

```bash
uv run pytest
```

Build the legacy executable:

```bash
uv run build
```

The generated output is placed in:

```text
dist/
```

## Usage

1. Start the app.
2. Select your `UE4SS/Mods` folder if it was not detected automatically.
3. Review the mod list.
4. Use the checkbox next to each mod to enable or disable it.
5. Use **Toggle all** to change all mods at once.
6. Drag a supported archive or folder into the window to install a new mod.
7. Use **Configure** on mods that expose `scripts/config.lua`.
8. Use **UE4SS Settings** to edit global UE4SS settings.
9. Pick one or more save strategies in the footer.
10. Click **Save Changes**.

## Troubleshooting

### The App Does Not Find My Mods Folder

Select it manually with **Select Mods Directory**.

Make sure you select:

```text
UE4SS/Mods
```

Do not select:

- the game root
- the `UE4SS` folder itself
- a single mod folder
- a downloads folder

### A Mod Does Not Appear

Check that the mod has a valid UE4SS structure:

```text
ModName/scripts/main.lua
```

or:

```text
ModName/dlls/main.dll
```

Folders without `main.lua` or `main.dll` are ignored.

### Drag-and-Drop Install Fails

Check that the dropped item is one of:

- a mod folder
- `.zip`
- `.7z`
- `.rar`

If the package has several unrelated folders or extra files before the real mod folder, the manager rejects it to avoid installing the wrong folder.

### Linux Build Fails with WebKit or GTK Errors

Install the Linux system dependencies for your distribution. Tauri v2 uses WebKitGTK on Linux, and development packages such as `libwebkit2gtk-4.1-dev`, `libgtk-3-dev`, and `pkg-config` are required.

### Linux Cross-Compile from Windows Fails

Building Linux Tauri apps from Windows is not the same as compiling plain Rust code. You need a Linux sysroot, C compiler, `pkg-config`, and Linux WebKit/GTK development libraries configured for cross-compilation.

The simpler path is to build Linux releases on Linux or in a Linux CI environment.

### Game Launch Does Not Find the Executable

The launcher searches nearby parent folders for common Unreal shipping executables:

- Windows: `Win64-Shipping.exe`, `WinGDK-Shipping.exe`
- Linux: `Linux-Shipping`, `Linux-Shipping.exe`, and Windows shipping executables for Proton-style layouts
- macOS: `.app` bundles and `Mac-Shipping`

If the game uses a non-standard layout, start the game manually.

## Project Layout

```text
.
├── ui/                    # Vite frontend
│   ├── index.html
│   ├── main.js
│   └── style.css
├── src-tauri/             # Tauri/Rust app
│   ├── src/
│   │   ├── commands.rs    # Tauri IPC commands
│   │   ├── error.rs       # Error types exposed to the UI
│   │   └── mod_manager/   # Mod scanning, install, config parsing
│   ├── Cargo.toml
│   └── tauri.conf.json
├── src/                   # Legacy Python implementation
├── tests/                 # Python tests
├── package.json
└── README.md
```

## Development Notes

- Keep frontend code in `ui/`.
- Keep Tauri command glue in `src-tauri/src/commands.rs`.
- Keep mod-management behavior in `src-tauri/src/mod_manager/service.rs`.
- Keep UI-visible error messages in `src-tauri/src/error.rs`.
- Run `npm run build` before shipping frontend changes.
- Run `cargo check` or `cargo test` before shipping backend changes.

## Contributing

Contributions are welcome.

1. Fork the project.
2. Create a branch:

   ```bash
   git checkout -b feature/your-change
   ```

3. Make your changes.
4. Run the relevant checks:

   ```bash
   npm run build
   cd src-tauri
   cargo check
   cargo test
   ```

5. Commit with a clear message.
6. Open a pull request.

## License

MIT. See [LICENSE](LICENSE) for details.

## Security

See [SECURITY.md](SECURITY.md) for reporting security issues.
