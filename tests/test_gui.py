# ruff: noqa: PLR6301, S101
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.common.gui import find_game_executable


class GameExecutableTests(unittest.TestCase):
	"""Tests for game executable discovery."""

	def test_finds_first_sorted_shipping_executable_one_directory_up(self) -> None:
		"""The first sorted Win64 shipping executable in the parent directory is used."""
		with TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			current_dir = root / "UE4SS"
			current_dir.mkdir()
			(root / "ZGame-Win64-Shipping.exe").write_text("", encoding="utf-8")
			expected = root / "AGame-Win64-Shipping.exe"
			expected.write_text("", encoding="utf-8")

			assert find_game_executable(current_dir) == expected

	def test_returns_none_when_no_shipping_executable_exists(self) -> None:
		"""Missing game executables are reported as absent."""
		with TemporaryDirectory() as temp_dir:
			current_dir = Path(temp_dir) / "UE4SS"
			current_dir.mkdir()

			assert find_game_executable(current_dir) is None


if __name__ == "__main__":
	unittest.main()
