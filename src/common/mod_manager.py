from json import dumps, load
from pathlib import Path
from shutil import copytree, move, rmtree
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from loguru import logger

from src.common.exceptions import InvalidModFolderException
from src.common.mod import UE4SSMod


class UE4SSModManager:
	"""Manages the loading and enabling/disabling of UE4SS mods."""

	NATIVE_MODS = (
		"BPML_GenericFunctions",
		"BPModLoaderMod",
		"CheatManagerEnablerMod",
		"ConsoleCommandsMod",
		"ConsoleEnablerMod",
		"Keybinds",
		"ConsoleCommands",
	)

	def __init__(self, path: Path) -> None:
		"""
		Initializes the UE4SSModManager with the given path.

		Args:
			path: The path to the mod folder.

		Raises:
			InvalidModFolderException: If the path is not a directory or does not have the correct folder structure.
		"""
		self.path = path

		enabled_overrides = self._get_enabled_overrides()

		if not path.is_dir() or not path.exists() or not self._has_right_folder_structure(path):
			raise InvalidModFolderException(f"Path {path} is not a directory.")

		self.mods = self.load_mods(enabled_overrides)

	def _get_enabled_overrides(self) -> list[str]:
		output = []

		if (self.path / "mods.txt").exists():
			with Path.open(self.path / "mods.txt", encoding="utf-8") as f:
				output += [line.strip() for line in f.readlines() if line.strip().endswith("1")]

		if (self.path / "mods.json").exists():
			with Path.open(self.path / "mods.json", encoding="utf-8-sig") as f:
				data = load(f)
				output += [mod["mod_name"] for mod in data if mod.get("mod_enabled", False)]

		return output

	@staticmethod
	def _has_right_folder_structure(path: Path) -> bool:
		"""
		Checks if the given path has the correct folder structure for the root mod folder.

		Args:
			path: The path to check.

		Returns:
			Whether the path has the correct folder structure.
		"""
		return path.stem.upper() == "MODS" and path.parent.stem.upper() == "UE4SS"

	def load_mods(self, enabled_overrides: list[str] | None = None) -> list[UE4SSMod]:
		"""
		Loads all mods from the specified path.

		Returns:
			A list of UE4SSMod objects representing the mods in the directory.
		"""
		output = []

		if enabled_overrides is None:
			enabled_overrides = []

		for mod_path in self.path.iterdir():
			if mod_path.is_dir() and mod_path.stem.upper() != "SHARED":
				try:
					override_enabled = mod_path.stem in enabled_overrides
					mod = UE4SSMod.from_path(mod_path, override_enabled=override_enabled)
					if mod:
						mod.is_native = mod.name in self.NATIVE_MODS
						output.append(mod)
				except Exception:
					logger.exception(f"Failed to load mod from {mod_path}. This mod will be skipped.")
					continue

		return output

	def install_mod_folder(self, source_path: Path, *, replace: bool = False) -> UE4SSMod:
		"""Install a mod folder into the managed Mods directory and enable it.

		Returns:
			The installed and enabled mod.

		Raises:
			FileExistsError: If the mod already exists and replace is false.
		"""
		source_path = source_path.resolve()
		mod = UE4SSMod.from_path(source_path)
		target_path = (self.path / source_path.name).resolve()

		if source_path == target_path:
			mod.enable()
			return mod

		if target_path.exists() and not replace:
			raise FileExistsError(f"Mod {source_path.name} already exists.")

		if target_path.exists():
			rmtree(target_path)

		copytree(source_path, target_path)
		installed_mod = UE4SSMod.from_path(target_path)
		installed_mod.enable()
		return installed_mod

	def install_mod_archive(self, source_path: Path, *, replace: bool = False) -> UE4SSMod:
		"""Install a zipped mod archive into the managed Mods directory.

		Returns:
			The installed and enabled mod.

		Raises:
			ValueError: If the zip contains unsafe paths.
		"""
		with TemporaryDirectory() as temp_dir:
			extract_path = Path(temp_dir)

			with ZipFile(source_path) as archive:
				for name in archive.namelist():
					path = Path(name)
					if path.is_absolute() or ".." in path.parts:
						raise ValueError(f"Unsafe zip entry: {name}")

				archive.extractall(extract_path)

			mod_path = self._archive_mod_path(extract_path, source_path.stem)
			return self.install_mod_folder(mod_path, replace=replace)

	@staticmethod
	def _archive_mod_path(extract_path: Path, archive_name: str) -> Path:
		if any(child.is_dir() and child.name.lower() == "scripts" for child in extract_path.iterdir()):
			mod_path = extract_path / archive_name
			mod_path.mkdir()
			for child in list(extract_path.iterdir()):
				if child != mod_path:
					move(str(child), mod_path / child.name)
			return mod_path

		folders = [child for child in extract_path.iterdir() if child.is_dir()]
		if len(folders) == 1:
			return folders[0]

		return extract_path

	def enable_mods(self, mod_names: list[str]) -> None:
		"""Enables the specified mods by creating enabled.txt files."""
		for mod in self.mods:
			if mod.name in mod_names:
				mod.enable()

	def disable_mods(self, mod_names: list[str]) -> None:
		"""Disables the specified mods by deleting enabled.txt files."""
		for mod in self.mods:
			if mod.name in mod_names:
				mod.disable()

	def _write_to_mods_json(self, mods: list[UE4SSMod]) -> None:
		"""
		Writes the enabled mods to the mods.json file.

		Args:
			mods: A list of UE4SSMod objects to write to the mods.json file.
		"""
		output = [{"mod_name": mod.name, "mod_enabled": mod.enabled} for mod in mods if mod.enabled]
		json_path = self.path / "mods.json"

		if json_path.exists():
			json_path.unlink()

		with Path.open(json_path, "w", encoding="utf-8") as f:
			f.write(dumps(output, indent=4, ensure_ascii=False))
			logger.debug(f"Enabled mods written to {json_path}")

	def _write_to_mods_txt(self, mods: list[UE4SSMod]) -> None:
		"""
		Writes the enabled mods to the mods.txt file.

		Args:
			mods: A list of UE4SSMod objects to write to the mods.txt file.
		"""
		output = [f"{mod.name} : 1\n" for mod in mods if mod.enabled]
		txt_path = self.path / "mods.txt"

		if txt_path.exists():
			txt_path.unlink()

		with Path.open(txt_path, "w", encoding="utf-8") as f:
			f.writelines(output)
			logger.debug(f"Enabled mods written to {txt_path}")

	def parse_mods(
		self,
		mods: list[UE4SSMod],
		*,
		save_enabled_txt: bool = True,
		save_mods_json: bool = True,
		save_mods_txt: bool = True,
	) -> None:
		"""
		Parses the mods and sets their enabled status.

		Args:
			mods: A list of UE4SSMod objects to parse.
			save_enabled_txt: Whether to save the enabled status to the enabled.txt files
			save_mods_json: Whether to save the enabled status to the mods.json file
			save_mods_txt: Whether to save the enabled status to the mods.txt file
		"""
		enabled_mods = [mod for mod in mods if mod.enabled]
		disabled_mods = [mod for mod in mods if not mod.enabled]

		if save_mods_json:
			self._write_to_mods_json(enabled_mods)

		if save_mods_txt:
			self._write_to_mods_txt(enabled_mods)

		if save_enabled_txt:
			if enabled_mods:
				for mod in enabled_mods:
					mod.enable()

			if disabled_mods:
				for mod in disabled_mods:
					mod.disable()

		logger.debug(f"Parsed {len(mods)} mods.")

	@property
	def enabled_mods(self) -> list[UE4SSMod]:
		"""Returns a list of enabled mods."""
		return [mod.name for mod in self.mods if mod.enabled]

	@property
	def disabled_mods(self) -> list[UE4SSMod]:
		"""Returns a list of disabled mods."""
		return [mod.name for mod in self.mods if not mod.enabled]

	@property
	def all_mods(self) -> list[UE4SSMod]:
		"""Returns a list of all mods."""
		return [mod.name for mod in self.mods]
