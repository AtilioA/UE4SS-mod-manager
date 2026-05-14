# ruff: noqa: DOC201, DOC501, PLR6301, S101
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from src.common.mod_manager import UE4SSModManager


def create_mods_path(root: Path) -> Path:
	"""Create a valid UE4SS Mods directory for tests."""
	mods_path = root / "UE4SS" / "Mods"
	mods_path.mkdir(parents=True)
	return mods_path


class UE4SSModManagerArchiveTests(unittest.TestCase):
	"""Tests for zipped mod installation."""

	def test_installs_zip_with_mod_folder(self) -> None:
		"""A zip containing a mod folder installs that folder."""
		with TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			manager = UE4SSModManager(create_mods_path(root))
			archive_path = root / "download.zip"

			with ZipFile(archive_path, "w") as archive:
				archive.writestr("ExampleMod/scripts/main.lua", "")

			mod = manager.install_mod_archive(archive_path)

			assert mod.name == "ExampleMod"
			assert (manager.path / "ExampleMod" / "scripts" / "main.lua").exists()
			assert (manager.path / "ExampleMod" / "enabled.txt").exists()

	def test_installs_zip_with_root_scripts_in_zip_named_folder(self) -> None:
		"""A zip with root scripts/ gets wrapped in a folder named after the zip."""
		with TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			manager = UE4SSModManager(create_mods_path(root))
			archive_path = root / "ArchiveMod.zip"

			with ZipFile(archive_path, "w") as archive:
				archive.writestr("scripts/main.lua", "")

			mod = manager.install_mod_archive(archive_path)

			assert mod.name == "ArchiveMod"
			assert (manager.path / "ArchiveMod" / "scripts" / "main.lua").exists()
			assert (manager.path / "ArchiveMod" / "enabled.txt").exists()

	def test_installing_existing_archive_mod_requires_replace(self) -> None:
		"""Archive installs use existing duplicate-mod protection."""
		with TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			manager = UE4SSModManager(create_mods_path(root))
			archive_path = root / "ArchiveMod.zip"

			(manager.path / "ArchiveMod" / "scripts").mkdir(parents=True)
			(manager.path / "ArchiveMod" / "scripts" / "main.lua").write_text("", encoding="utf-8")

			with ZipFile(archive_path, "w") as archive:
				archive.writestr("scripts/main.lua", "")

			try:
				manager.install_mod_archive(archive_path)
			except FileExistsError:
				return

			raise AssertionError("Expected FileExistsError")


if __name__ == "__main__":
	unittest.main()
