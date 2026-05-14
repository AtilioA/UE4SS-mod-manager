# ruff: noqa: DOC501, PLR6301, S101
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.common.config import LuaConfigDocument
from src.common.config_validation import ConfigValidationError, validate_config_value

CONFIG_TEXT = """return {
	Enabled = true,

	TargetFOV = 95.0,
	Name = "Wide FOV",

	-- F7 toggles the FOV reapply behavior on/off.
	EnableToggleHotkey = false, -- inline comment
	Unsupported = { Nested = true },
}
"""


class LuaConfigDocumentTests(unittest.TestCase):
	"""Tests for restricted config.lua parsing and saving."""

	def test_parses_supported_top_level_values(self) -> None:
		"""Supported scalar fields are parsed and unsupported fields are ignored."""
		document = LuaConfigDocument.from_text(CONFIG_TEXT)
		entries = {entry.key: entry for entry in document.entries}

		assert entries["Enabled"].value is True
		assert entries["Enabled"].value_type == "boolean"
		assert entries["TargetFOV"].value == "95.0"
		assert entries["TargetFOV"].value_type == "number"
		assert entries["Name"].value == "Wide FOV"
		assert entries["Name"].value_type == "string"
		assert entries["EnableToggleHotkey"].comment == "F7 toggles the FOV reapply behavior on/off."
		assert "Unsupported" not in entries

	def test_nil_values_are_supported(self) -> None:
		"""Nil settings are exposed and preserved instead of skipped."""
		with TemporaryDirectory() as temp_dir:
			config_path = Path(temp_dir) / "config.lua"
			config_path.write_text(
				"""return {
	OptionalValue = nil,
}
""",
				encoding="utf-8",
			)

			document = LuaConfigDocument.from_path(config_path)

			assert document.entries[0].key == "OptionalValue"
			assert document.entries[0].value is None
			assert document.entries[0].value_type == "nil"

			document.save({"OptionalValue": None})

			assert (
				config_path.read_text(encoding="utf-8")
				== """return {
	OptionalValue = nil,
}
"""
			)

	def test_multiline_contiguous_comments_are_used_as_label(self) -> None:
		"""Contiguous comments immediately above a setting are joined into one label."""
		document = LuaConfigDocument.from_text("""return {
	-- Reapply periodically because games can reset camera values after loading,
	-- entering vehicles, using tools, respawning, or rebuilding camera state.
	ReapplyEveryMilliseconds = 5000,
}
""")

		assert document.entries[0].comment == (
			"Reapply periodically because games can reset camera values after loading,\n"
			"entering vehicles, using tools, respawning, or rebuilding camera state."
		)

	def test_non_contiguous_comments_are_not_used_as_label(self) -> None:
		"""A blank line breaks comment association with the next setting."""
		document = LuaConfigDocument.from_text("""return {
	-- This comment belongs to no setting.

	Enabled = true,
}
""")

		assert not document.entries[0].comment

	def test_save_replaces_only_supported_value_tokens(self) -> None:
		"""Saving updates only literal tokens and preserves surrounding text."""
		with TemporaryDirectory() as temp_dir:
			config_path = Path(temp_dir) / "config.lua"
			config_path.write_text(CONFIG_TEXT, encoding="utf-8")

			document = LuaConfigDocument.from_path(config_path)
			document.save({"Enabled": False, "TargetFOV": "100.5", "Name": "Narrow FOV"})

			assert (
				config_path.read_text(encoding="utf-8")
				== """return {
	Enabled = false,

	TargetFOV = 100.5,
	Name = "Narrow FOV",

	-- F7 toggles the FOV reapply behavior on/off.
	EnableToggleHotkey = false, -- inline comment
	Unsupported = { Nested = true },
}
"""
			)

	def test_nested_tables_and_expressions_are_ignored(self) -> None:
		"""Nested scalars and Lua expressions are not exposed as editable fields."""
		text = """return {
	TopLevel = true,
	Computed = 1 + 2,
	Nested = {
		Enabled = false,
	},
}
"""
		document = LuaConfigDocument.from_text(text)
		entries = {entry.key: entry for entry in document.entries}

		assert set(entries) == {"TopLevel"}

	def test_partial_save_preserves_untouched_values_and_escapes_strings(self) -> None:
		"""Partial updates preserve omitted values and write escaped string literals."""
		with TemporaryDirectory() as temp_dir:
			config_path = Path(temp_dir) / "config.lua"
			config_path.write_text(
				"""return {
	Enabled = true,
	Name = 'Wide\\nFOV',
	Path = "C:\\\\Mods",
}
""",
				encoding="utf-8",
			)

			document = LuaConfigDocument.from_path(config_path)
			document.save({"Name": "Narrow\nFOV"})

			assert (
				config_path.read_text(encoding="utf-8")
				== """return {
	Enabled = true,
	Name = 'Narrow\\nFOV',
	Path = "C:\\\\Mods",
}
"""
			)

	def test_duplicate_keys_only_expose_first_entry(self) -> None:
		"""Duplicate keys are not all mutated through one UI field."""
		document = LuaConfigDocument.from_text("""return {
	Enabled = true,
	Enabled = false,
}
""")

		assert len(document.entries) == 1
		assert document.entries[0].value is True

	def test_invalid_number_is_rejected(self) -> None:
		"""Invalid numeric UI input is rejected before saving."""
		try:
			validate_config_value("fast", "number")
		except ConfigValidationError:
			return

		raise AssertionError("Expected ConfigValidationError")

	def test_boolean_requires_boolean_value(self) -> None:
		"""Boolean validation rejects truthy strings."""
		try:
			validate_config_value("true", "boolean")
		except ConfigValidationError:
			return

		raise AssertionError("Expected ConfigValidationError")

	def test_valid_numbers_are_normalized(self) -> None:
		"""Valid number strings are stripped and preserved as strings."""
		assert validate_config_value("  1e3 ", "number") == "1e3"


if __name__ == "__main__":
	unittest.main()
