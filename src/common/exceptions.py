class InvalidModException(ValueError):  # noqa: N818
	"""Exception raised for invalid mod definitions."""


class InvalidModFolderException(ValueError):  # noqa: N818
	"""Exception raised for an invalid mod folder."""


class ModAlreadyExistsError(FileExistsError):
	"""Exception raised when installing a mod over an existing managed mod."""

	def __init__(self, mod_name: str) -> None:
		"""Initialize with the resolved mod folder name."""
		self.mod_name = mod_name
		super().__init__(f"Mod {mod_name} already exists.")
