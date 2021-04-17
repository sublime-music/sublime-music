"""
This file contains all of the classes related for a shared server configuration form.
"""

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from time import sleep
from typing import Any, Callable, cast, Dict, Iterable, Optional, Tuple, Type, Union

import bleach

from gi.repository import GLib, GObject, Gtk, Pango

from . import ConfigurationStore


@dataclass
class ConfigParamDescriptor:
    """
    Describes a parameter that can be used to configure an adapter. The
    :class:`description`, :class:`required` and :class:`default:` should be self-evident
    as to what they do.

    The :class:`helptext` parameter is optional detailed text that will be shown in a
    help bubble corresponding to the field.

    The :class:`type` must be one of the following:

    * The literal type ``str``: corresponds to a freeform text entry field in the UI.
    * The literal type ``bool``: corresponds to a toggle in the UI.
    * The literal type ``int``: corresponds to a numeric input in the UI.
    * The literal string ``"password"``: corresponds to a password entry field in the
      UI.
    * The literal string ``"option"``: corresponds to dropdown in the UI.
    * The literal type ``Path``: corresponds to a file picker in the UI.

    The :class:`advanced` parameter specifies whether the setting should be behind an
    "Advanced" expander.

    The :class:`numeric_bounds` parameter only has an effect if the :class:`type` is
    `int`. It specifies the min and max values that the UI control can have.

    The :class:`numeric_step` parameter only has an effect if the :class:`type` is
    `int`. It specifies the step that will be taken using the "+" and "-" buttons on the
    UI control (if supported).

    The :class:`options` parameter only has an effect if the :class:`type` is
    ``"option"``. It specifies the list of options that will be available in the
    dropdown in the UI.

    The :class:`pathtype` parameter only has an effect if the :class:`type` is
    ``Path``. It can be either ``"file"`` or ``"directory"`` corresponding to a file
    picker and a directory picker, respectively.
    """

    type: Union[Type, str]
    description: str
    required: bool = True
    helptext: Optional[str] = None
    advanced: Optional[bool] = None
    default: Any = None
    numeric_bounds: Optional[Tuple[int, int]] = None
    numeric_step: Optional[int] = None
    options: Optional[Iterable[str]] = None
    pathtype: Optional[str] = None


class ConfigureServerForm(Gtk.Box):
    __gsignals__ = {
        "config-valid-changed": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (bool,),
        ),
    }

    def __init__(
        self,
        config_store: ConfigurationStore,
        config_parameters: Dict[str, ConfigParamDescriptor],
        verify_configuration: Callable[[], Dict[str, Optional[str]]],
        is_networked: bool = True,
    ):
        """
        Inititialize a :class:`ConfigureServerForm` with the given configuration
        parameters.

        :param config_store: The :class:`ConfigurationStore` to use to store
            configuration values for this adapter.
        :param config_parameters: An dictionary where the keys are the name of the
            configuration paramter and the values are the :class:`ConfigParamDescriptor`
            object corresponding to that configuration parameter. The order of the keys
            in the dictionary correspond to the order that the configuration parameters
            will be shown in the UI.
        :param verify_configuration: A function that verifies whether or not the
            current state of the ``config_store`` is valid. The output should be a
            dictionary containing verification errors. The keys of the returned
            dictionary should be the same as the keys passed in via the
            ``config_parameters`` parameter. The values should be strings describing
            why the corresponding value in the ``config_store`` is invalid.

            If the adapter ``is_networked``, and the special ``"__ping__"`` key is
            returned, then the error will be shown below all of the other settings in
            the ping status box.
        :param is_networked: whether or not the adapter is networked.
        """
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.config_store = config_store
        self.required_config_parameter_keys = set()
        self.verify_configuration = verify_configuration
        self.entries = {}
        self.is_networked = is_networked

        content_grid = Gtk.Grid(
            column_spacing=10,
            row_spacing=5,
            margin_left=10,
            margin_right=10,
        )
        advanced_grid = Gtk.Grid(column_spacing=10, row_spacing=10)

        def create_string_input(is_password: bool, key: str) -> Gtk.Entry:
            entry = Gtk.Entry(
                text=cast(
                    Callable[[str], None],
                    (config_store.get_secret if is_password else config_store.get),
                )(key),
                hexpand=True,
            )
            if is_password:
                entry.set_visibility(False)

            entry.connect(
                "changed",
                lambda e: self._on_config_change(key, e.get_text(), secret=is_password),
            )
            return entry

        def create_bool_input(key: str) -> Gtk.Switch:
            switch = Gtk.Switch(active=config_store.get(key), halign=Gtk.Align.START)
            switch.connect(
                "notify::active",
                lambda s, _: self._on_config_change(key, s.get_active()),
            )
            return switch

        def create_int_input(key: str) -> Gtk.SpinButton:
            raise NotImplementedError()

        def create_option_input(key: str) -> Gtk.ComboBox:
            raise NotImplementedError()

        def create_path_input(key: str) -> Gtk.FileChooser:
            raise NotImplementedError()

        content_grid_i = 0
        advanced_grid_i = 0
        for key, cpd in config_parameters.items():
            if cpd.required:
                self.required_config_parameter_keys.add(key)
            if cpd.default is not None:
                config_store[key] = config_store.get(key, cpd.default)

            label = Gtk.Label(label=cpd.description, halign=Gtk.Align.END)

            input_el_box = Gtk.Box()
            self.entries[key] = cast(
                Callable[[str], Gtk.Widget],
                {
                    str: partial(create_string_input, False),
                    "password": partial(create_string_input, True),
                    bool: create_bool_input,
                    int: create_int_input,
                    "option": create_option_input,
                    Path: create_path_input,
                }[cpd.type],
            )(key)
            input_el_box.add(self.entries[key])

            if cpd.helptext:
                help_icon = Gtk.Image.new_from_icon_name(
                    "help-about",
                    Gtk.IconSize.BUTTON,
                )
                help_icon.get_style_context().add_class("configure-form-help-icon")
                help_icon.set_tooltip_markup(cpd.helptext)
                input_el_box.add(help_icon)

            if not cpd.advanced:
                content_grid.attach(label, 0, content_grid_i, 1, 1)
                content_grid.attach(input_el_box, 1, content_grid_i, 1, 1)
                content_grid_i += 1
            else:
                advanced_grid.attach(label, 0, advanced_grid_i, 1, 1)
                advanced_grid.attach(input_el_box, 1, advanced_grid_i, 1, 1)
                advanced_grid_i += 1

        # Add a button and revealer for the advanced section of the configuration.
        if advanced_grid_i > 0:
            advanced_component = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

            advanced_expander = Gtk.Revealer()
            advanced_expander_icon = Gtk.Image.new_from_icon_name(
                "go-down-symbolic", Gtk.IconSize.BUTTON
            )
            revealed = False

            def toggle_expander(*args):
                nonlocal revealed
                revealed = not revealed
                advanced_expander.set_reveal_child(revealed)
                icon_dir = "up" if revealed else "down"
                advanced_expander_icon.set_from_icon_name(
                    f"go-{icon_dir}-symbolic", Gtk.IconSize.BUTTON
                )

            advanced_expander_button = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
            advanced_expander_button_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=10
            )

            advanced_label = Gtk.Label(
                label="<b>Advanced Settings</b>", use_markup=True
            )
            advanced_expander_button_box.add(advanced_label)
            advanced_expander_button_box.add(advanced_expander_icon)

            advanced_expander_button.add(advanced_expander_button_box)
            advanced_expander_button.connect("clicked", toggle_expander)
            advanced_component.add(advanced_expander_button)

            advanced_expander.add(advanced_grid)
            advanced_component.add(advanced_expander)

            content_grid.attach(advanced_component, 0, content_grid_i, 2, 1)
            content_grid_i += 1

        content_grid.attach(
            Gtk.Separator(name="config-verification-separator"), 0, content_grid_i, 2, 1
        )
        content_grid_i += 1

        self.config_verification_box = Gtk.Box(spacing=10)
        content_grid.attach(self.config_verification_box, 0, content_grid_i, 2, 1)

        self.pack_start(content_grid, False, False, 10)
        self._verification_status_ratchet = 0
        self._verify_config(self._verification_status_ratchet)

    had_all_required_keys = False
    verifying_in_progress = False

    def _set_verification_status(
        self, verifying: bool, is_valid: bool = False, error_text: str = None
    ):
        if verifying:
            if not self.verifying_in_progress:
                for c in self.config_verification_box.get_children():
                    self.config_verification_box.remove(c)
                self.config_verification_box.add(
                    Gtk.Spinner(active=True, name="verify-config-spinner")
                )
                self.config_verification_box.add(
                    Gtk.Label(
                        label="<b>Verifying configuration...</b>", use_markup=True
                    )
                )
            self.verifying_in_progress = True
        else:
            self.verifying_in_progress = False
            for c in self.config_verification_box.get_children():
                self.config_verification_box.remove(c)

            def set_icon_and_label(icon_name: str, label_text: str):
                self.config_verification_box.add(
                    Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DND)
                )
                label = Gtk.Label(
                    label=label_text,
                    use_markup=True,
                    ellipsize=Pango.EllipsizeMode.END,
                )
                label.set_tooltip_markup(label_text)
                self.config_verification_box.add(label)

            if is_valid:
                set_icon_and_label(
                    "config-ok-symbolic", "<b>Configuration is valid</b>"
                )
            elif escaped := bleach.clean(error_text or ""):
                set_icon_and_label("config-error-symbolic", escaped)

        self.config_verification_box.show_all()

    def _on_config_change(self, key: str, value: Any, secret: bool = False):
        if secret:
            self.config_store.set_secret(key, value)
        else:
            self.config_store[key] = value
        self._verification_status_ratchet += 1
        self._verify_config(self._verification_status_ratchet)

    def _verify_config(self, ratchet: int):
        self.emit("config-valid-changed", False)

        from sublime_music.adapters import Result

        if self.required_config_parameter_keys.issubset(set(self.config_store.keys())):
            if self._verification_status_ratchet != ratchet:
                return

            self._set_verification_status(True)

            has_empty = False
            if self.had_all_required_keys:
                for key in self.required_config_parameter_keys:
                    if self.config_store.get(key) == "":
                        self.entries[key].get_style_context().add_class("invalid")
                        self.entries[key].set_tooltip_markup("This field is required")
                        has_empty = True
                    else:
                        self.entries[key].get_style_context().remove_class("invalid")
                        self.entries[key].set_tooltip_markup(None)

            self.had_all_required_keys = True
            if has_empty:
                self._set_verification_status(
                    False,
                    error_text="<b>There are missing fields</b>\n"
                    "Please fill out all required fields.",
                )
                return

            def on_verify_result(verification_errors: Dict[str, Optional[str]]):
                if self._verification_status_ratchet != ratchet:
                    return

                if len(verification_errors) == 0:
                    self.emit("config-valid-changed", True)
                    for entry in self.entries.values():
                        entry.get_style_context().remove_class("invalid")
                    self._set_verification_status(False, is_valid=True)
                    return

                for key, entry in self.entries.items():
                    if error_text := verification_errors.get(key):
                        entry.get_style_context().add_class("invalid")
                        entry.set_tooltip_markup(error_text)
                    else:
                        entry.get_style_context().remove_class("invalid")
                        entry.set_tooltip_markup(None)

                self._set_verification_status(
                    False, error_text=verification_errors.get("__ping__")
                )

            def verify_with_delay() -> Dict[str, Optional[str]]:
                sleep(0.75)
                if self._verification_status_ratchet != ratchet:
                    return {}

                return self.verify_configuration()

            errors_result: Result[Dict[str, Optional[str]]] = Result(verify_with_delay)
            errors_result.add_done_callback(
                lambda f: GLib.idle_add(on_verify_result, f.result())
            )
