from pathlib import Path

import PyInstaller.__main__
import tkinterdnd2


def _tkinterdnd2_windows_data_args() -> list[str]:
    package_path = Path(tkinterdnd2.__file__).parent
    return [
        f"--add-data={package_path / 'tkdnd' / platform};tkinterdnd2/tkdnd/{platform}"
        for platform in ("win-arm64", "win-x64", "win-x86")
    ]


def main() -> None:
    """Build the standalone Windows executable."""
    PyInstaller.__main__.run(
        [
            "src/main.py",
            "--name=UE4SS-ModManager",
            "--onefile",
            "--noconfirm",
            "--clean",
            "--noconsole",
            "--icon=assets/img/ue.ico",
            "--add-data=assets/img;assets/img",
            "--exclude-module=PIL._avif",
            "--exclude-module=PIL._webp",
            "--exclude-module=PIL._imagingcms",
            "--exclude-module=ssl",
            "--exclude-module=_ssl",
            "--exclude-module=_hashlib",
            *_tkinterdnd2_windows_data_args(),
        ],
    )


if __name__ == "__main__":
    main()
