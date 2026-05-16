import subprocess
from collections.abc import Callable
from pathlib import Path

import customtkinter as ctk
from loguru import logger
from PIL import Image

try:
	from tkinterdnd2 import COPY, DND_FILES, TkinterDnD
except ImportError:
	COPY = "copy"
	DND_FILES = None
	TkinterDnD = None

from src.common.config import LuaConfigDocument
from src.common.config_validation import ConfigValidationError, ConfigValue, validate_config_value
from src.common.exceptions import ModAlreadyExistsError
from src.common.mod import UE4SSMod
from src.common.mod_manager import UE4SSModManager

_DND_BASE = TkinterDnD.DnDWrapper if TkinterDnD else object
_POPUP_TEXT_FONT_SIZE = 14
_WARNING_POPUP_GEOMETRY = "560x240"
_WARNING_POPUP_WRAP_LENGTH = 500
_ERROR_POPUP_GEOMETRY = "460x220"
_ERROR_POPUP_WRAP_LENGTH = 400
_GAME_EXECUTABLE_SUFFIXES = ("Win64-Shipping.exe", "WinGDK-Shipping.exe")


def find_game_executable(current_dir: Path | None = None) -> Path | None:
	"""Find the first game executable above the UE4SS or UE4SS/Mods directory.

	Returns:
		The first sorted matching executable in the first or second parent directory, or None when no match exists.
	"""
	start_dir = current_dir or Path.cwd()
	for search_dir in (start_dir.parent, start_dir.parent.parent):
		matches = sorted(
			(
				path
				for path in search_dir.glob("*Shipping.exe")
				if path.is_file() and path.name.endswith(_GAME_EXECUTABLE_SUFFIXES)
			),
			key=lambda path: path.name.lower(),
		)
		if matches:
			return matches[0]
	return None


class ToolTip:
	"""Simple ToolTip for CustomTkinter widgets."""

	def __init__(self, widget: object, text: str) -> None:
		"""Initialize the ToolTip."""
		self.widget = widget
		self.text = text
		self.tooltip_window = None
		self.widget.bind("<Enter>", self.enter)
		self.widget.bind("<Leave>", self.leave)

	def enter(self, event: object = None) -> None:
		"""Schedule tooltip appearance on mouse enter."""
		self.schedule_id = self.widget.after(100, self.show_tooltip)

	def leave(self, event: object = None) -> None:
		"""Cancel schedule and hide tooltip on mouse leave."""
		if hasattr(self, "schedule_id"):
			self.widget.after_cancel(self.schedule_id)
		self.hide_tooltip()

	def show_tooltip(self) -> None:
		"""Show the tooltip window."""
		if self.tooltip_window or not self.text:
			return
		x = self.widget.winfo_rootx() + 25
		y = self.widget.winfo_rooty() + 30
		self.tooltip_window = tw = ctk.CTkToplevel(self.widget)
		tw.wm_overrideredirect(True)
		tw.wm_geometry(f"+{x}+{y}")

		label = ctk.CTkLabel(
			tw,
			text=self.text,
			justify="left",
			fg_color=("gray85", "gray25"),
			corner_radius=4,
			padx=5,
			pady=3,
			font=ctk.CTkFont(size=11),
		)
		label.pack()

	def hide_tooltip(self) -> None:
		"""Hide and destroy the tooltip window."""
		tw = self.tooltip_window
		self.tooltip_window = None
		if tw:
			tw.destroy()


class UE4SSModManagerGUI(ctk.CTk, _DND_BASE):
	"""A GUI for managing UE4SS mods."""

	def __init__(
		self,
		mod_manager: UE4SSModManager,
		logo_path: Path | None = None,
		icon_path: Path | None = None,
	) -> None:
		"""Initialize the UE4SSModManagerGUI."""
		super().__init__()

		self.mod_manager = mod_manager
		self.initial_mod_states = {mod.name: mod.enabled for mod in mod_manager.mods}
		self.mod_checkboxes = {}
		self.show_native_warning_shown = False
		self.drag_and_drop_enabled = False

		self._setup_window(icon_path)
		self._setup_theme()

		self.main_frame = ctk.CTkFrame(self)
		self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)

		self._create_header(logo_path)
		self._create_search_filter()
		self._create_controls()
		self._create_mod_list()
		self._create_save_options()
		self._create_status_bar()

		self.populate_mod_list()
		self._setup_drag_and_drop()
		self.update_save_button_state()

	def _setup_drag_and_drop(self) -> None:
		"""Allow users to drop a mod folder or zip archive onto the app to install it."""
		if TkinterDnD is None or DND_FILES is None:
			logger.warning("tkinterdnd2 is not available; drag and drop is disabled.")
			return

		try:
			self.TkdndVersion = TkinterDnD._require(self)
			self.drag_and_drop_enabled = True
			self._register_drop_target(self)
			self.status_bar.configure(text=f"{self.status_bar.cget('text')}. Drop a mod folder or zip to install.")
		except Exception as e:
			logger.warning(f"Failed to enable drag and drop: {e}")

	def _register_drop_target(self, widget: object) -> None:
		"""Register a widget and its children as mod folder drop targets."""
		if DND_FILES is None:
			return

		widget.drop_target_register(DND_FILES)
		widget.dnd_bind("<<Drop>>", self.handle_mod_folder_drop)

		for child in widget.winfo_children():
			self._register_drop_target(child)

	def _setup_window(self, icon_path: Path | None = None) -> None:
		"""Configure the window properties."""
		self.title("Subnautica 2 UE4SS Mod Manager")

		# Make window size dynamic based on screen size
		screen_width = self.winfo_screenwidth()
		screen_height = self.winfo_screenheight()
		window_width = int(screen_width * 0.6)
		window_height = int(screen_height * 0.6)
		self.minsize(window_width, window_height)

		self.attributes("-topmost", True)
		self.after(100, lambda: self.attributes("-topmost", False))
		self.center_window()

		if icon_path and icon_path.exists():
			try:
				self.iconbitmap(icon_path)
				logger.debug(f"Set window icon: {icon_path}")
			except Exception as e:
				logger.error(f"Failed to set window icon: {e}")

	@staticmethod
	def _setup_theme() -> None:
		"""Set up the application theme."""
		ctk.set_appearance_mode("dark")
		ctk.set_default_color_theme("blue")

	def _create_header(self, logo_path: Path | None = None) -> None:
		"""Create the header with logo or title."""
		if logo_path and logo_path.exists():
			try:
				pil_image = Image.open(logo_path)
				logo_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(180, 54))
				self.logo_label = ctk.CTkLabel(self.main_frame, image=logo_image, text="")
				self.logo_label.pack(pady=(15, 15))
				logger.debug(f"Set logo image: {logo_path}")
			except Exception as e:
				logger.error(f"Failed to load logo image: {e}")
				self._create_title_label()
		else:
			self._create_title_label()

		self.header_frame = ctk.CTkFrame(self.main_frame)
		self.header_frame.pack(fill="x", padx=10, pady=(0, 5))
		self.separator1 = ctk.CTkFrame(self.main_frame, height=1, fg_color="gray30")
		self.separator1.pack(fill="x", padx=10, pady=3)

	def _create_title_label(self) -> None:
		"""Create the title label if no logo is available."""
		self.title_label = ctk.CTkLabel(
			self.main_frame,
			text="Subnautica 2 UE4SS Mod Manager",
			font=ctk.CTkFont(size=24, weight="bold"),
		)
		self.title_label.pack(pady=(15, 15))

	def _create_search_filter(self) -> None:
		"""Create the search filter components."""
		self.list_label = ctk.CTkLabel(
			self.header_frame,
			text="Available mods:",
			font=ctk.CTkFont(size=16, weight="bold"),
		)
		self.list_label.pack(side="left", padx=10, pady=5)

		self.search_var = ctk.StringVar()
		self.search_var.trace_add("write", lambda *_: self.filter_mods())
		self.search_entry = ctk.CTkEntry(
			self.header_frame,
			placeholder_text="Search mods...",
			textvariable=self.search_var,
			width=200,
		)
		self.search_entry.pack(side="left", padx=10, pady=5)

		self.show_native_mods_var = ctk.BooleanVar(value=False)
		self.show_native_switch = ctk.CTkSwitch(
			self.header_frame,
			text="Show native mods",
			variable=self.show_native_mods_var,
			onvalue=True,
			offvalue=False,
			command=self.toggle_native_mods_visibility,
		)
		self.show_native_switch.pack(side="right", padx=10, pady=5)

	def _create_controls(self) -> None:
		"""Create the control buttons section."""
		self.controls_frame = ctk.CTkFrame(self.main_frame)
		self.controls_frame.pack(fill="x", padx=10, pady=(0, 5))

		self.toggle_all_var = ctk.BooleanVar(value=False)
		self.toggle_all_checkbox = ctk.CTkCheckBox(
			self.controls_frame,
			text="Toggle all",
			variable=self.toggle_all_var,
			onvalue=True,
			offvalue=False,
			command=self.toggle_all_mods,
			width=24,
		)
		self.toggle_all_checkbox.pack(side="left", padx=10, pady=5)

		self.refresh_button = ctk.CTkButton(
			self.controls_frame,
			text="Refresh list",
			command=self.refresh_mods,
			width=80,
		)
		self.refresh_button.pack(side="right", padx=5, pady=5)

		self.reset_button = ctk.CTkButton(
			self.controls_frame,
			text="Undo",
			command=self.reset_mods,
			width=80,
		)
		self.reset_button.pack(side="right", padx=5, pady=5)

		self.launch_game_button = ctk.CTkButton(
			self.controls_frame,
			text="Launch game",
			command=self.launch_game,
			width=110,
		)
		self.launch_game_button.pack(side="right", padx=5, pady=5)

	def _create_mod_list(self) -> None:
		"""Create the scrollable mod list area."""
		self.mod_list_frame = ctk.CTkScrollableFrame(self.main_frame)
		self.mod_list_frame.pack(fill="both", expand=True, padx=10, pady=8)
		self.separator2 = ctk.CTkFrame(self.main_frame, height=1, fg_color="gray30")
		self.separator2.pack(fill="x", padx=10, pady=3)

	def _create_save_options(self) -> None:
		"""Create the save options section."""
		self.save_options_frame = ctk.CTkFrame(self.main_frame)
		self.save_options_frame.pack(fill="x", padx=10, pady=(8, 0))

		self.save_enabled_txt_var = ctk.BooleanVar(value=True)
		self.save_enabled_txt = ctk.CTkSwitch(
			self.save_options_frame,
			text="Save enabled.txt",
			variable=self.save_enabled_txt_var,
			onvalue=True,
			offvalue=False,
			command=self.update_save_button_state,
			width=24,
		)
		self.save_enabled_txt.pack(side="left", padx=10, pady=8)
		ToolTip(self.save_enabled_txt, "enabled.txt method is fine for most load orders")

		self.save_mods_json_var = ctk.BooleanVar(value=False)
		self.save_mods_json = ctk.CTkSwitch(
			self.save_options_frame,
			text="Save mods.json",
			variable=self.save_mods_json_var,
			onvalue=True,
			offvalue=False,
			command=lambda: self.handle_save_option_change(self.save_mods_json_var),
			width=24,
		)
		self.save_mods_json.pack(side="left", padx=10, pady=8)

		self.save_mods_txt_var = ctk.BooleanVar(value=False)
		self.save_mods_txt = ctk.CTkSwitch(
			self.save_options_frame,
			text="Save mods.txt",
			variable=self.save_mods_txt_var,
			onvalue=True,
			offvalue=False,
			command=lambda: self.handle_save_option_change(self.save_mods_txt_var),
			width=24,
		)
		self.save_mods_txt.pack(side="left", padx=10, pady=8)

		self.spacer = ctk.CTkLabel(self.save_options_frame, text="")
		self.spacer.pack(side="left", fill="x", expand=True)

		self.save_button = ctk.CTkButton(
			self.save_options_frame,
			text="Save Changes",
			command=self.save_changes,
			width=120,
			text_color_disabled=("gray55", "gray60"),
			state="disabled",
		)
		self.save_button_colors = {
			"normal": {
				"fg_color": self.save_button.cget("fg_color"),
				"hover_color": self.save_button.cget("hover_color"),
			},
			"disabled": {
				"fg_color": ("gray75", "gray35"),
				"hover_color": ("gray75", "gray35"),
			},
		}
		self.save_button.pack(side="right", padx=10, pady=8)

	def _create_status_bar(self) -> None:
		"""Create the status bar at the bottom."""
		self.status_bar = ctk.CTkLabel(
			self.main_frame,
			text=f"Loaded {len(self.mod_manager.mods)} mods",
			font=ctk.CTkFont(size=12),
		)
		self.status_bar.pack(padx=10, pady=(8, 0), anchor="w")

	def toggle_native_mods_visibility(self) -> None:
		"""Toggle visibility of native mods with a warning."""
		if self.show_native_mods_var.get() and not self.show_native_warning_shown:
			self.show_warning(
				"Warning",
				"You should be absolutely sure about toggling UE4SS native mods. "
				"Disabling essential native mods may break UE4SS functionality.",
				self.populate_mod_list,
				lambda: self.show_native_mods_var.set(False),
			)
			self.show_native_warning_shown = True
		else:
			self.populate_mod_list()

	def update_save_button_state(self) -> None:
		"""Update the save button state based on save options."""
		has_changes = self.initial_mod_states != self.get_mod_status()
		has_save_target = (
			self.save_enabled_txt_var.get() or self.save_mods_json_var.get() or self.save_mods_txt_var.get()
		)
		self._set_save_button_state("normal" if has_changes and has_save_target else "disabled")

	def _set_save_button_state(self, state: str) -> None:
		"""Apply save button state and matching theme colors."""
		colors = self.save_button_colors[state]
		self.save_button.configure(
			**colors,
			state=state,
		)

	def refresh_mods(self) -> None:
		"""Reload mods from disk."""
		try:
			self.mod_manager.mods = self.mod_manager.load_mods()
			self.initial_mod_states = {mod.name: mod.enabled for mod in self.mod_manager.mods}
			self.populate_mod_list()

			self.status_bar.configure(text=f"Refreshed {len(self.mod_manager.mods)} mods")

		except Exception as e:
			logger.exception(f"Error refreshing mods: {e}")
			self.show_error("Error Refreshing Mods", str(e))

	def launch_game(self) -> None:
		"""Launch the first game executable found above the ue4ss or ue4ss/Mods directory."""
		try:
			game_executable = find_game_executable()
			if game_executable is None:
				self.show_error(
					"Game not found",
					f"No executable ending with Win64-Shipping.exe or WinGDK-Shipping.exe was found above {Path.cwd()}.",
				)
				return

			subprocess.Popen([str(game_executable)], cwd=game_executable.parent)
			self.status_bar.configure(text=f"Launched {game_executable.name}.")
		except Exception as e:
			logger.exception(f"Error launching game: {e}")
			self.show_error("Error launching game", str(e))

	def handle_mod_folder_drop(self, event: object) -> str:
		"""Install and enable a dropped UE4SS mod folder or zip archive.

		Returns:
			The DND action accepted by the drop handler.
		"""
		try:
			dropped_paths = [Path(path) for path in self.tk.splitlist(getattr(event, "data", ""))]
			if len(dropped_paths) != 1:
				self.show_error("Invalid drop", "Drop exactly one mod folder or zip file.")
				return COPY

			source_path = dropped_paths[0]
			if not source_path.is_dir() and source_path.suffix.lower() != ".zip":
				self.show_error("Invalid drop", "Drop a mod folder or zip file.")
				return COPY

			self.install_dropped_mod(source_path)
		except Exception as e:
			logger.exception(f"Error handling dropped mod folder: {e}")
			self.show_error("Install failed", str(e))

		return COPY

	def install_dropped_mod(self, source_path: Path, *, replace: bool = False) -> None:
		"""Install a dropped mod folder or zip archive, enable it, and refresh the UI."""
		try:
			if source_path.is_dir():
				installed_mod = self.mod_manager.install_mod_folder(source_path, replace=replace)
			else:
				installed_mod = self.mod_manager.install_mod_archive(source_path, replace=replace)
			self.mod_manager.mods = self.mod_manager.load_mods()
			self.initial_mod_states = {mod.name: mod.enabled for mod in self.mod_manager.mods}
			self.populate_mod_list()
			self.status_bar.configure(text=f"Installed and enabled {installed_mod.name}.")
			self.update_save_button_state()
		except ModAlreadyExistsError as e:
			if replace:
				logger.exception(f"Error installing dropped mod folder: {e}")
				self.show_error("Install failed", str(e))
				return

			self.show_replace_mod_warning(e.mod_name, lambda: self.install_dropped_mod(source_path, replace=True))
		except Exception as e:
			logger.exception(f"Error installing dropped mod folder: {e}")
			self.show_error("Install failed", str(e))

	def show_replace_mod_warning(self, mod_name: str, on_ok: Callable[[], None]) -> None:
		"""Confirm replacing an existing mod using the parsed mod folder name."""
		self.show_warning(
			"Update/Replace mod?",
			f"{mod_name} already exists.\nReplace the entire folder and enable the new files?",
			on_ok,
			lambda: None,
		)

	def populate_mod_list(self) -> None:
		"""Populate the mod list with checkboxes for each mod."""
		try:
			for widget in self.mod_list_frame.winfo_children():
				widget.destroy()

			self.mod_checkboxes = {}

			for mod in self.mod_manager.mods:
				if not self.show_native_mods_var.get() and mod.is_native:
					continue

				frame = ctk.CTkFrame(self.mod_list_frame)
				frame.pack(fill="x", padx=5, pady=2)

				checkbox = ctk.CTkCheckBox(
					frame,
					text=f"{'[NATIVE] ' if mod.is_native else ''}{mod.name}",
					variable=ctk.BooleanVar(value=mod.enabled),
					command=self.update_save_button_state,
					onvalue=True,
					offvalue=False,
					width=24,
				)
				checkbox.pack(side="left", padx=10, pady=5)

				script_count = ctk.CTkLabel(
					frame,
					text=f"{len(mod.scripts)} script(s)",
					font=ctk.CTkFont(size=12),
					text_color="gray",
				)
				script_count.pack(side="right", padx=10, pady=5)

				if mod.has_config:
					config_button = ctk.CTkButton(
						frame,
						text="Configure mod",
						command=lambda selected_mod=mod: self.show_config_window(selected_mod),
						width=32,
					)
					config_button.pack(side="right", padx=5, pady=5)

				self.mod_checkboxes[mod.name] = checkbox

			visible_count = sum(
				1 for mod in self.mod_manager.mods if not mod.is_native or self.show_native_mods_var.get()
			)
			enabled_count = sum(
				1
				for mod in self.mod_manager.mods
				if mod.enabled and (not mod.is_native or self.show_native_mods_var.get())
			)
			if self.drag_and_drop_enabled:
				self._register_drop_target(self.mod_list_frame)

			self.status_bar.configure(text=f"Showing {visible_count} mods ({enabled_count} enabled)")

		except Exception as e:
			logger.exception(f"Error saving changes: {e}")
			self.show_error("Error Saving Changes", str(e))

	def handle_save_option_change(self, var: ctk.BooleanVar) -> None:
		"""Handle changes to save options with warnings."""
		if var.get():
			self.show_warning(
				"Warning",
				"Are you absolutely sure about writing to these files? "
				"This can potentially break your UE4SS installation.",
				lambda: None,  # Do nothing on OK
				lambda: var.set(False),  # Reset on Cancel
			)

		self.update_save_button_state()

	def reset_mods(self) -> None:
		"""Reset mods to their initial states when the app was launched."""
		try:
			for mod_name, checkbox in self.mod_checkboxes.items():
				initial_state = self.initial_mod_states.get(mod_name, False)
				if initial_state:
					checkbox.select()
				else:
					checkbox.deselect()

			self.status_bar.configure(text="Mods reset to initial state. Click Save to apply.")

		except Exception as e:
			logger.exception(f"Error resetting mods: {e}")
			self.show_error("Error Resetting Mods", str(e))

	def show_config_window(self, mod: UE4SSMod) -> None:
		"""Show a config editor for supported scripts/config.lua values."""
		if not mod.config_path:
			self.show_error("Missing Config", f"{mod.name} does not have a scripts/config.lua file.")
			return

		try:
			document = LuaConfigDocument.from_path(mod.config_path)
		except Exception as e:
			logger.exception(f"Error loading config for {mod.name}: {e}")
			self.show_error("Error Loading Config", str(e))
			return

		if not document.entries:
			self.show_error(
				"Unsupported Config",
				"No supported top-level boolean, number, or string values were found.",
			)
			return

		config_window, fields_frame, button_frame = self._create_config_window(mod)
		field_vars = self._create_config_fields(fields_frame, document)

		cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=config_window.destroy, width=100)
		cancel_button.pack(side="left", padx=10, pady=10)

		save_button = ctk.CTkButton(
			button_frame,
			text="Save",
			command=lambda: self._save_config_window(mod, document, field_vars, config_window),
			width=100,
		)
		save_button.pack(side="right", padx=10, pady=10)

	def _create_config_window(self, mod: UE4SSMod) -> tuple[ctk.CTkToplevel, ctk.CTkScrollableFrame, ctk.CTkFrame]:
		config_window = ctk.CTkToplevel(self)
		config_window.title(f"Configure {mod.name}")
		config_window.geometry("520x480")
		config_window.transient(self)
		config_window.grab_set()
		config_window.attributes("-topmost", True)  # noqa: FBT003
		config_window.after(100, lambda: config_window.attributes("-topmost", False))  # noqa: FBT003

		frame = ctk.CTkFrame(config_window)
		frame.pack(fill="both", expand=True, padx=20, pady=20)

		title = ctk.CTkLabel(frame, text=f"Configure {mod.name}", font=ctk.CTkFont(size=18, weight="bold"))
		title.pack(anchor="w", padx=10, pady=(15, 10))

		config_path_label = ctk.CTkLabel(
			frame,
			text=str(mod.config_path),
			font=ctk.CTkFont(size=11),
			text_color="gray",
		)
		config_path_label.pack(anchor="w", padx=10, pady=(0, 10))

		fields_frame = ctk.CTkScrollableFrame(frame)
		fields_frame.pack(fill="both", expand=True, padx=10, pady=5)

		button_frame = ctk.CTkFrame(frame)
		button_frame.pack(fill="x", padx=10, pady=(10, 5))
		return config_window, fields_frame, button_frame

	@staticmethod
	def _create_config_fields(
		fields_frame: ctk.CTkScrollableFrame,
		document: LuaConfigDocument,
	) -> dict[str, ctk.BooleanVar | ctk.StringVar]:
		field_vars: dict[str, ctk.BooleanVar | ctk.StringVar] = {}
		for entry in document.entries:
			row = ctk.CTkFrame(fields_frame)
			row.pack(fill="x", padx=4, pady=5)
			row.grid_columnconfigure(0, minsize=250)
			row.grid_columnconfigure(1, weight=1)

			label_frame = ctk.CTkFrame(row, fg_color="transparent")
			label_frame.grid(row=0, column=0, sticky="nw", padx=(12, 16), pady=10)

			label = ctk.CTkLabel(label_frame, text=entry.key, anchor="w", font=ctk.CTkFont(weight="bold"))
			label.pack(fill="x", anchor="w")

			if entry.comment:
				description = ctk.CTkLabel(
					label_frame,
					text=entry.comment,
					anchor="w",
					justify="left",
					wraplength=230,
					font=ctk.CTkFont(size=11),
					text_color="gray",
				)
				description.pack(fill="x", anchor="w", pady=(2, 0))

			if entry.value_type == "boolean":
				var = ctk.BooleanVar(value=bool(entry.value))
				field = ctk.CTkSwitch(row, text="", variable=var, onvalue=True, offvalue=False, width=24)
				field_sticky = "w"
			elif entry.value_type == "nil":
				var = ctk.StringVar(value="nil")
				field = ctk.CTkEntry(row, textvariable=var, state="disabled")
				field_sticky = "ew"
			else:
				var = ctk.StringVar(value=str(entry.value))
				field = ctk.CTkEntry(row, textvariable=var)
				field_sticky = "ew"

			field.grid(row=0, column=1, sticky=field_sticky, padx=(0, 12), pady=10)
			field_vars[entry.key] = var

		return field_vars

	@staticmethod
	def _collect_config_updates(
		document: LuaConfigDocument,
		field_vars: dict[str, ctk.BooleanVar | ctk.StringVar],
	) -> dict[str, ConfigValue]:
		updates: dict[str, ConfigValue] = {}
		for entry in document.entries:
			updates[entry.key] = validate_config_value(field_vars[entry.key].get(), entry.value_type)

		return updates

	def _save_config_window(
		self,
		mod: UE4SSMod,
		document: LuaConfigDocument,
		field_vars: dict[str, ctk.BooleanVar | ctk.StringVar],
		config_window: ctk.CTkToplevel,
	) -> None:
		try:
			document.save(self._collect_config_updates(document, field_vars))
		except ConfigValidationError as e:
			self.show_error("Invalid config value", str(e))
			return
		except Exception as e:
			logger.exception(f"Error saving config for {mod.name}: {e}")
			self.show_error("Error saving config", str(e))
			return

		self.status_bar.configure(text=f"Saved config for {mod.name}.")
		config_window.destroy()

	def show_warning(self, title: str, message: str, on_ok: Callable[[], None], on_cancel: Callable[[], None]) -> None:
		"""Show a warning popup with OK and Cancel buttons."""
		warning_window = ctk.CTkToplevel(self)
		warning_window.title(title)
		warning_window.geometry(_WARNING_POPUP_GEOMETRY)
		warning_window.transient(self)
		warning_window.grab_set()
		warning_window.attributes("-topmost", True)
		warning_window.after(100, lambda: warning_window.attributes("-topmost", False))
		warning_window.update_idletasks()
		width = warning_window.winfo_width()
		height = warning_window.winfo_height()
		x = (warning_window.winfo_screenwidth() // 2) - (width // 2)
		y = (warning_window.winfo_screenheight() // 2) - (height // 2)
		warning_window.geometry(f"{width}x{height}+{x}+{y}")

		frame = ctk.CTkFrame(warning_window)
		frame.pack(fill="both", expand=True, padx=20, pady=20)

		warning_label = ctk.CTkLabel(
			frame,
			text=message,
			wraplength=_WARNING_POPUP_WRAP_LENGTH,
			justify="left",
			font=ctk.CTkFont(size=_POPUP_TEXT_FONT_SIZE),
		)
		warning_label.pack(padx=10, pady=(10, 20))

		button_frame = ctk.CTkFrame(frame)
		button_frame.pack(fill="x", padx=10, pady=(0, 10))

		cancel_button = ctk.CTkButton(
			button_frame,
			text="Cancel",
			command=lambda: (on_cancel(), warning_window.destroy()),
			width=100,
		)
		cancel_button.pack(side="left", padx=10, pady=10)

		ok_button = ctk.CTkButton(
			button_frame,
			text="OK",
			command=lambda: (on_ok(), warning_window.destroy()),
			width=100,
		)
		ok_button.pack(side="right", padx=10, pady=10)

	def get_mod_status(self) -> dict[str, bool]:
		"""
		Get the current status of all mods from the checkboxes.

		Returns:
			A mapping with mod names as keys and their enabled status as values.
		"""
		try:
			mod_status = {}
			for mod in self.mod_manager.mods:
				checkbox = self.mod_checkboxes.get(mod.name)
				if checkbox:
					mod_status[mod.name] = checkbox.get()

		except Exception as e:
			logger.exception(f"Error getting mod status: {e}")
			self.show_error("Error Getting Mod Status", str(e))
			return {}

		else:
			return mod_status

	def get_mod_objects(self) -> list[UE4SSMod]:
		"""
		Get the current status of all mods from the checkboxes.

		Returns:
			A list of UE4SSMod objects with updated enabled status
		"""
		try:
			updated_mods = []

			for mod in self.mod_manager.mods:
				checkbox = self.mod_checkboxes.get(mod.name)

				if checkbox:
					logger.debug(f"Mod: {mod.name}, Enabled: {checkbox.get()}")
					updated_mod = UE4SSMod(
						name=mod.name,
						path=mod.path,
						enabled=checkbox.get(),
						scripts=mod.scripts,
						is_native=mod.is_native,
						lang=mod.lang,
						config_path=mod.config_path,
					)
					updated_mods.append(updated_mod)

		except Exception as e:
			logger.exception(f"Error saving changes: {e}")
			self.show_error("Error Saving Changes", str(e))
			return []

		else:
			return updated_mods

	def save_changes(self) -> None:
		"""Save the changes to the mods."""
		try:
			updated_mods = self.get_mod_objects()
			self.mod_manager.parse_mods(
				mods=updated_mods,
				save_enabled_txt=self.save_enabled_txt_var.get(),
				save_mods_json=self.save_mods_json_var.get(),
				save_mods_txt=self.save_mods_txt_var.get(),
			)

			enabled_count = sum(1 for mod in updated_mods if mod.enabled)
			self.status_bar.configure(text=f"Changes saved. {enabled_count}/{len(updated_mods)} mods enabled.")

			self.initial_mod_states = self.get_mod_status()
			self.update_save_button_state()

		except Exception as e:
			logger.exception(f"Error saving changes: {e}")
			self.show_error("Error Saving Changes", str(e))

	def toggle_all_mods(self) -> None:
		"""Toggle all mods on or off based on the Toggle All checkbox."""
		try:
			new_state = self.toggle_all_var.get()

			for checkbox in self.mod_checkboxes.values():
				if new_state:
					checkbox.select()
				else:
					checkbox.deselect()

			self.status_bar.configure(text=f"All mods {'enabled' if new_state else 'disabled'}. Click Save to apply.")

		except Exception as e:
			logger.exception(f"Error toggling mods: {e}")
			self.show_error("Error Toggling Mods", str(e))

	def filter_mods(self) -> None:
		"""Filter mods based on search text."""
		search_text = self.search_var.get().lower()

		for mod_name, checkbox in self.mod_checkboxes.items():
			parent_frame = checkbox.master
			if search_text in mod_name.lower():
				parent_frame.pack(fill="x", padx=5, pady=2)
			else:
				parent_frame.pack_forget()

	def center_window(self) -> None:
		"""Center the window on the screen."""
		self.update_idletasks()
		width = self.winfo_width()
		height = self.winfo_height()
		x = (self.winfo_screenwidth() // 2) - (width // 2)
		y = (self.winfo_screenheight() // 2) - (height // 2)
		self.geometry(f"{width}x{height}+{x}+{y}")

	def show_error(self, title: str, message: str) -> None:
		"""Show an error popup with the given title and message."""
		error_window = ctk.CTkToplevel(self)
		error_window.title(title)
		error_window.geometry(_ERROR_POPUP_GEOMETRY)
		error_window.transient(self)
		error_window.grab_set()
		error_window.attributes("-topmost", True)
		error_window.after(100, lambda: error_window.attributes("-topmost", False))
		error_window.update_idletasks()
		width = error_window.winfo_width()
		height = error_window.winfo_height()
		x = (error_window.winfo_screenwidth() // 2) - (width // 2)
		y = (error_window.winfo_screenheight() // 2) - (height // 2)
		error_window.geometry(f"{width}x{height}+{x}+{y}")

		frame = ctk.CTkFrame(error_window)
		frame.pack(fill="both", expand=True, padx=20, pady=20)

		error_label = ctk.CTkLabel(
			frame,
			text=message,
			wraplength=_ERROR_POPUP_WRAP_LENGTH,
			justify="left",
			font=ctk.CTkFont(size=_POPUP_TEXT_FONT_SIZE),
		)
		error_label.pack(padx=10, pady=(10, 20))

		ok_button = ctk.CTkButton(frame, text="OK", command=error_window.destroy, width=100)
		ok_button.pack(pady=(0, 10))


def start_gui(mod_manager: UE4SSModManager, logo_path: Path | None = None, icon_path: Path | None = None) -> None:
	"""
	Start the GUI with the given mod manager.

	Args:
		mod_manager: An instance of UE4SSModManager
		logo_path: Path to the logo image file
		icon_path: Path to the icon file (.ico)
	"""
	app = UE4SSModManagerGUI(mod_manager, logo_path, icon_path)
	app.mainloop()
