# UE4SS Mod Manager

A GUI application for managing [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) mods in Unreal Engine games.

## Features

- Enable/disable mods with a single click
- Toggle all mods on/off with one button
- Drag and drop a mod folder or zip to install and enable it
- Configurable save options:
  - Individual `enabled.txt` files
  - `mods.json` for UE4SS
  - `mods.txt` for UE4SS
- Modern dark mode UI
- Simple, intuitive interface

---

## Installation

### Option 1: Pre-built executable

1. Download the latest release from the [Nexus page](https://www.nexusmods.com/subnautica2/mods/34)
2. Place the executable in your game's `ue4ss/Mods` folder
3. Run it

### Option 2: Build from source (Tauri)

This is the recommended build path. The app is built with [Tauri v2](https://tauri.app/) (Rust backend + Vite frontend).

#### Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| [Node.js](https://nodejs.org/) | 18 or newer | https://nodejs.org/ |
| [Rust](https://www.rust-lang.org/tools/install) | stable (latest) | https://rustup.rs/ |
| [WebView2](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) | any | Pre-installed on Windows 10/11 |

> **Windows users:** During Rust installation via `rustup`, make sure to also install the **MSVC build tools** (Visual Studio Build Tools with the "Desktop development with C++" workload).

#### Steps

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-username/UE4SS-mod-manager.git
   cd UE4SS-mod-manager
   ```

2. **Install Node dependencies**

   ```bash
   npm install
   ```

3. **Build the app**

   ```bash
   npm run tauri build
   ```

   This will:
   - Build the Vite frontend (`dist/`)
   - Compile the Rust backend
   - Bundle everything into a Windows installer and standalone `.exe`

4. **Find the output**

   The built files are placed in:

   ```
   src-tauri/target/release/bundle/
   ├── msi/          ← Windows installer (.msi)
   ├── nsis/         ← NSIS installer (.exe)
   └── ue4ss-modmanager.exe   ← standalone executable
   ```

   Place the `.exe` in your game's `ue4ss/Mods` folder and run it.

#### Development mode (hot reload)

To run the app locally with live reloading:

```bash
npm run tauri dev
```

This starts the Vite dev server and opens the Tauri window. Changes to the frontend are reflected instantly.

---

### Option 3: Build from source (Python / legacy)

The original Python/Tkinter version is still available.

#### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

#### Steps

```bash
uv sync
uv run build
```

The executable will be created in `dist/`. Move it to your game's `ue4ss/Mods` folder.

---

## Usage

1. Launch the application
2. All mods in your `UE4SS/Mods` folder are automatically detected
3. Enable/disable mods by checking/unchecking their boxes
4. Drag a mod folder or zip onto the window to install and enable it
5. Configure save options:
   - **Save enabled.txt** — updates individual `enabled.txt` files per mod
   - **Save mods.json** — updates the `mods.json` file used by UE4SS
   - **Save mods.txt** — updates the `mods.txt` file used by UE4SS
6. Click **Save Changes** to apply
7. Use **Toggle All** to enable/disable all mods at once

## How it works

- The manager scans the `UE4SS/Mods` directory for mod folders
- Each mod must have a `scripts/` folder containing at least one `main.lua` file
- Folder and zip installs handle simple nested structures automatically
- Enabling a mod creates an `enabled.txt` in its folder and adds entries to `mods.json` / `mods.txt`
- Disabling a mod removes those entries

---

## Development

### Setup (Tauri)

```bash
npm install
npm run tauri dev
```

### Setup (Python)

```bash
uv sync --dev
pre-commit install
```

---

## Contributing

Contributions are welcome!

1. Fork the project
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add some amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## License

MIT — see [LICENSE](LICENSE) for details.

## Security

See [SECURITY.md](SECURITY.md) for reporting security issues.
