import PyInstaller.__main__


def main() -> None:
    """Build the standalone Windows executable."""
    PyInstaller.__main__.run([
        "src/main.py",
        "--name=UE4SS-ModManager",
        "--onefile",
        "--noconfirm",
        "--noconsole",
        "--icon=assets/img/ue.ico",
        "--add-data=assets/img;assets/img",
        "--collect-data=tkinterdnd2",
    ])


if __name__ == "__main__":
    main()
