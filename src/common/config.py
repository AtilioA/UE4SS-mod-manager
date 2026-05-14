from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.common.config_validation import ConfigValidationError, ConfigValue, ConfigValueType, format_lua_value

ASSIGNMENT_PATTERN = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)")


@dataclass(frozen=True)
class LuaConfigEntry:
	"""A supported top-level scalar value in a UE4SS config.lua file."""

	key: str
	value: ConfigValue
	value_type: ConfigValueType
	line_index: int
	value_start: int
	value_end: int
	quote: str = '"'
	comment: str = ""


@dataclass
class LuaConfigDocument:
	"""Restricted line-preserving representation of a Lua config table."""

	path: Path
	lines: list[str]
	entries: list[LuaConfigEntry]

	@classmethod
	def from_path(cls, path: Path) -> LuaConfigDocument:
		"""Load and parse supported values from config.lua.

		Returns:
			A parsed config document.
		"""
		return cls.from_text(path.read_text(encoding="utf-8-sig"), path=path)

	@classmethod
	def from_text(cls, text: str, *, path: Path | None = None) -> LuaConfigDocument:
		"""Parse supported top-level config assignments from reading Lua.

		Returns:
			A parsed config document.
		"""
		lines = text.splitlines(keepends=True)
		entries = []
		seen_keys = set()
		pending_comments = []
		table_depth = 0

		for line_index, line in enumerate(lines):
			if table_depth == 1:
				comment = _parse_comment_line(line)
				if comment is not None:
					pending_comments.append(comment)
				else:
					entry = _parse_line(line, line_index, comment="\n".join(pending_comments))
					if entry and entry.key not in seen_keys:
						seen_keys.add(entry.key)
						entries.append(entry)

					pending_comments = []
			else:
				pending_comments = []

			table_depth += _table_depth_delta(line)
			table_depth = max(table_depth, 0)

		return cls(path=path or Path("config.lua"), lines=lines, entries=entries)

	def save(self, updates: dict[str, ConfigValue]) -> None:
		"""Write updated supported values while preserving all other text."""
		updated_lines = self.lines.copy()

		for entry in reversed(self.entries):
			if entry.key not in updates:
				continue

			value = format_lua_value(updates[entry.key], entry.value_type, quote=entry.quote)
			line = updated_lines[entry.line_index]
			updated_lines[entry.line_index] = f"{line[: entry.value_start]}{value}{line[entry.value_end :]}"

		self.path.write_text("".join(updated_lines), encoding="utf-8")


def _parse_line(line: str, line_index: int, *, comment: str = "") -> LuaConfigEntry | None:
	stripped = line.lstrip()
	if stripped.startswith(("--", "return", "}")):
		return None

	match = ASSIGNMENT_PATTERN.match(line)
	if not match:
		return None

	key = match.group(2)
	token_start, token_end = _read_value_token(line, match.end())
	if token_start == token_end:
		return None

	token = line[token_start:token_end]
	try:
		value, value_type, quote = _parse_value_token(token)
	except ConfigValidationError:
		return None

	return LuaConfigEntry(
		key=key,
		value=value,
		value_type=value_type,
		line_index=line_index,
		value_start=token_start,
		value_end=token_end,
		quote=quote,
		comment=comment,
	)


def _parse_comment_line(line: str) -> str | None:
	stripped = line.strip()
	if not stripped.startswith("--"):
		return None

	return stripped[2:].strip()


def _read_value_token(line: str, start: int) -> tuple[int, int]:
	line_without_newline = line.rstrip("\r\n")
	index = start
	while index < len(line_without_newline) and line_without_newline[index].isspace():
		index += 1

	if index >= len(line_without_newline):
		return index, index

	if line_without_newline[index] in {"'", '"'}:
		quote = line_without_newline[index]
		cursor = index + 1
		escaped = False
		while cursor < len(line_without_newline):
			char = line_without_newline[cursor]
			if char == quote and not escaped:
				end = cursor + 1
				return (index, end) if _has_only_value_terminator(line_without_newline[end:]) else (index, index)

			escaped = char == "\\" and not escaped
			if char != "\\":
				escaped = False
			cursor += 1

		return index, index

	cursor = index
	while cursor < len(line_without_newline):
		if line_without_newline[cursor] == "," or line_without_newline[cursor:].startswith("--"):
			break

		if line_without_newline[cursor].isspace():
			break

		cursor += 1

	return (index, cursor) if _has_only_value_terminator(line_without_newline[cursor:]) else (index, index)


def _has_only_value_terminator(trailer: str) -> bool:
	trailer = trailer.strip()
	if not trailer:
		return True

	if trailer.startswith("--"):
		return True

	if trailer.startswith(","):
		after_comma = trailer[1:].strip()
		return not after_comma or after_comma.startswith("--")

	return False


def _parse_value_token(token: str) -> tuple[ConfigValue, ConfigValueType, str]:
	lowered = token.lower()
	if lowered == "true":
		return True, "boolean", '"'

	if lowered == "false":
		return False, "boolean", '"'

	if lowered == "nil":
		return None, "nil", '"'

	if len(token) >= 2 and token[0] in {"'", '"'} and token[-1] == token[0]:
		return _unescape_lua_string(token[1:-1], token[0]), "string", token[0]

	format_lua_value(token, "number")
	return token, "number", '"'


def _unescape_lua_string(value: str, quote: str) -> str:
	# Decode only the Lua escapes this restricted editor can safely round-trip.
	output = []
	escaped = False
	for char in value:
		if escaped:
			output.append({"n": "\n", "r": "\r", "t": "\t", quote: quote, "\\": "\\"}.get(char, char))
			escaped = False
			continue

		if char == "\\":
			escaped = True
			continue

		output.append(char)

	if escaped:
		output.append("\\")

	return "".join(output)


def _table_depth_delta(line: str) -> int:
	# Naive Lua table parser.
	delta = 0
	quote = ""
	escaped = False
	index = 0
	while index < len(line):
		char = line[index]
		if not quote and line[index:].startswith("--"):
			break

		if quote:
			if char == quote and not escaped:
				quote = ""
			escaped = char == "\\" and not escaped
			if char != "\\":
				escaped = False
		elif char in {"'", '"'}:
			quote = char
		elif char == "{":
			delta += 1
		elif char == "}":
			delta -= 1

		index += 1

	return delta
