from __future__ import annotations

import re
from typing import Literal

ConfigValueType = Literal["boolean", "number", "string", "nil"]
ConfigValue = bool | str | None

NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


class ConfigValidationError(ValueError):
	"""Raised when a config value cannot be safely parsed or saved."""


def validate_config_value(value: object, value_type: ConfigValueType) -> ConfigValue:
	"""Validate and normalize a UI value for a restricted Lua config field.

	Returns:
		A normalized boolean or string value ready for Lua formatting.

	Raises:
		ConfigValidationError: If the value is not valid for the requested type.
	"""
	if value_type == "boolean":
		if isinstance(value, bool):
			return value

		raise ConfigValidationError("Expected a boolean value.")

	if value_type == "number":
		normalized = str(value).strip()
		if NUMBER_PATTERN.fullmatch(normalized):
			return normalized

		raise ConfigValidationError("Expected a number, like 95, 95.0, or 1e3.")

	if value_type == "string":
		return str(value)

	if value_type == "nil":
		if value in {None, "", "nil"}:
			return None

		raise ConfigValidationError("Expected nil.")

	raise ConfigValidationError(f"Unsupported config value type: {value_type}")


def format_lua_value(value: ConfigValue, value_type: ConfigValueType, *, quote: str = '"') -> str:
	"""Format a validated value as a Lua literal.

	Returns:
		A Lua literal string.

	"""
	validated = validate_config_value(value, value_type)

	if value_type == "boolean":
		return "true" if validated else "false"

	if value_type == "number":
		return str(validated)

	if value_type == "nil":
		return "nil"

	escaped = (
		str(validated)
		.replace("\\", "\\\\")
		.replace("\n", "\\n")
		.replace("\r", "\\r")
		.replace("\t", "\\t")
		.replace(quote, f"\\{quote}")
	)
	return f"{quote}{escaped}{quote}"
