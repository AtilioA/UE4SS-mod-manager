# ruff: noqa: PLR6301, S101
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.common.mod import UE4SSMod


class UE4SSModTests(unittest.TestCase):
	"""Tests for mod metadata detection."""

	def test_from_path_detects_scripts_config_lua(self) -> None:
		"""A scripts/config.lua file marks the mod configurable."""
		with TemporaryDirectory() as temp_dir:
			mod_path = Path(temp_dir) / "ExampleMod"
			scripts_path = mod_path / "scripts"
			scripts_path.mkdir(parents=True)
			(scripts_path / "main.lua").write_text("", encoding="utf-8")
			config_path = scripts_path / "config.lua"
			config_path.write_text("return { Enabled = true }", encoding="utf-8")

			mod = UE4SSMod.from_path(mod_path)

			assert mod is not None
			assert mod.has_config
			assert mod.config_path == config_path

	def test_from_path_detects_mixed_case_scripts_config_lua(self) -> None:
		"""Mixed-case scripts/config.lua filenames are treated as configurable."""
		with TemporaryDirectory() as temp_dir:
			mod_path = Path(temp_dir) / "ExampleMod"
			scripts_path = mod_path / "scripts"
			scripts_path.mkdir(parents=True)
			(scripts_path / "main.lua").write_text("", encoding="utf-8")
			config_path = scripts_path / "Config.LUA"
			config_path.write_text("return { Enabled = true }", encoding="utf-8")

			mod = UE4SSMod.from_path(mod_path)

			assert mod is not None
			assert mod.has_config
			assert mod.config_path == config_path

	def test_from_path_ignores_root_config_lua(self) -> None:
		"""A root-level config.lua is not treated as configurable by default."""
		with TemporaryDirectory() as temp_dir:
			mod_path = Path(temp_dir) / "ExampleMod"
			scripts_path = mod_path / "scripts"
			scripts_path.mkdir(parents=True)
			(scripts_path / "main.lua").write_text("", encoding="utf-8")
			(mod_path / "config.lua").write_text("return { Enabled = true }", encoding="utf-8")

			mod = UE4SSMod.from_path(mod_path)

			assert mod is not None
			assert not mod.has_config
			assert mod.config_path is None


if __name__ == "__main__":
	unittest.main()
