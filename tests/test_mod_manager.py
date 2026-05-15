# ruff: noqa: DOC201, DOC501, PLR6301, S101
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from src.common.exceptions import InvalidModException, ModAlreadyExistsError
from src.common.mod_manager import UE4SSModManager


def create_mods_path(root: Path) -> Path:
	"""Create a valid UE4SS Mods directory for tests."""
	mods_path = root / "UE4SS" / "Mods"
	mods_path.mkdir(parents=True)
	return mods_path


class UE4SSModManagerArchiveTests(unittest.TestCase):
	"""Tests for zipped mod installation."""

	def test_replaces_existing_mod_folder_entirely_when_requested(self) -> None:
		"""Replacing a folder install removes files from the previous copy."""
		with TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			manager = UE4SSModManager(create_mods_path(root))
			source_path = root / "downloads" / "ExampleMod"
			target_path = manager.path / "ExampleMod"

			(target_path / "scripts").mkdir(parents=True)
			(target_path / "scripts" / "main.lua").write_text("old", encoding="utf-8")
			(target_path / "scripts" / "stale.lua").write_text("stale", encoding="utf-8")
			(source_path / "scripts").mkdir(parents=True)
			(source_path / "scripts" / "main.lua").write_text("new", encoding="utf-8")

			mod = manager.install_mod_folder(source_path, replace=True)

			assert mod.name == "ExampleMod"
			assert (target_path / "scripts" / "main.lua").read_text(encoding="utf-8") == "new"
			assert not (target_path / "scripts" / "stale.lua").exists()
			assert (target_path / "enabled.txt").exists()

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

	def test_installs_folder_with_pure_nested_mod_structure(self) -> None:
		"""A folder that only nests the real mod folder is unwrapped during install."""
		with TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			manager = UE4SSModManager(create_mods_path(root))
			source_path = root / "UnzippedMod"
			nested_mod = source_path / "Subnautica2" / "Binaries" / "Win64" / "ue4ss" / "Mods" / "SN2ModSettings"
			(nested_mod / "Scripts").mkdir(parents=True)
			(nested_mod / "Scripts" / "main.lua").write_text("", encoding="utf-8")

			mod = manager.install_mod_folder(source_path)

			assert mod.name == "SN2ModSettings"
			assert (manager.path / "SN2ModSettings" / "Scripts" / "main.lua").exists()
			assert not (manager.path / "UnzippedMod").exists()
			assert (manager.path / "SN2ModSettings" / "enabled.txt").exists()

	def test_rejects_nested_folder_with_extra_files_before_mod_folder(self) -> None:
		"""Nested installs are only accepted when parent folders contain folders only."""
		with TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			manager = UE4SSModManager(create_mods_path(root))
			source_path = root / "UnzippedMod"
			nested_mod = source_path / "Wrapper" / "RealMod"
			(nested_mod / "scripts").mkdir(parents=True)
			(nested_mod / "scripts" / "main.lua").write_text("", encoding="utf-8")
			(source_path / "README.txt").write_text("extra", encoding="utf-8")

			try:
				manager.install_mod_folder(source_path)
			except InvalidModException:
				return

		raise AssertionError("Expected InvalidModException")

	def test_rejects_nested_folder_with_multiple_child_folders_before_mod_folder(self) -> None:
		"""Nested installs are rejected when traversal would be ambiguous."""
		with TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			manager = UE4SSModManager(create_mods_path(root))
			source_path = root / "UnzippedMod"
			nested_mod = source_path / "Wrapper" / "RealMod"
			(nested_mod / "scripts").mkdir(parents=True)
			(nested_mod / "scripts" / "main.lua").write_text("", encoding="utf-8")
			(source_path / "OtherFolder").mkdir(parents=True)

			try:
				manager.install_mod_folder(source_path)
			except InvalidModException:
				return

		raise AssertionError("Expected InvalidModException")

	def test_installs_zip_with_pure_nested_mod_structure(self) -> None:
		"""Archive installs use the same pure-folder unwrapping as folder installs."""
		with TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			manager = UE4SSModManager(create_mods_path(root))
			archive_path = root / "Nested.zip"

			with ZipFile(archive_path, "w") as archive:
				archive.writestr("Subnautica2/Binaries/Win64/ue4ss/Mods/SN2ModSettings/Scripts/main.lua", "")

			mod = manager.install_mod_archive(archive_path)

			assert mod.name == "SN2ModSettings"
			assert (manager.path / "SN2ModSettings" / "Scripts" / "main.lua").exists()
			assert (manager.path / "SN2ModSettings" / "enabled.txt").exists()

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

	def test_existing_nested_archive_mod_error_uses_resolved_mod_name(self) -> None:
		"""Duplicate archive warnings use the parsed mod folder instead of the archive name."""
		with TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			manager = UE4SSModManager(create_mods_path(root))
			archive_path = root / "SN2ModSettings V1.0-20-1-1778773091.zip"

			(manager.path / "SN2ModSettings" / "Scripts").mkdir(parents=True)
			(manager.path / "SN2ModSettings" / "Scripts" / "main.lua").write_text("", encoding="utf-8")

			with ZipFile(archive_path, "w") as archive:
				archive.writestr("Subnautica2/Binaries/Win64/ue4ss/Mods/SN2ModSettings/Scripts/main.lua", "")

			error = None
			try:
				manager.install_mod_archive(archive_path)
			except ModAlreadyExistsError as caught_error:
				error = caught_error

			assert error is not None
			assert error.mod_name == "SN2ModSettings"
			assert "SN2ModSettings" in str(error)
			assert archive_path.name not in str(error)

	def test_replaces_existing_archive_mod_entirely_when_requested(self) -> None:
		"""Replacing an archive install removes files from the previous copy."""
		with TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			manager = UE4SSModManager(create_mods_path(root))
			archive_path = root / "ArchiveMod.zip"
			target_path = manager.path / "ArchiveMod"

			(target_path / "scripts").mkdir(parents=True)
			(target_path / "scripts" / "main.lua").write_text("old", encoding="utf-8")
			(target_path / "scripts" / "stale.lua").write_text("stale", encoding="utf-8")

			with ZipFile(archive_path, "w") as archive:
				archive.writestr("scripts/main.lua", "new")

			mod = manager.install_mod_archive(archive_path, replace=True)

			assert mod.name == "ArchiveMod"
			assert (target_path / "scripts" / "main.lua").read_text(encoding="utf-8") == "new"
			assert not (target_path / "scripts" / "stale.lua").exists()
			assert (target_path / "enabled.txt").exists()


if __name__ == "__main__":
	unittest.main()
