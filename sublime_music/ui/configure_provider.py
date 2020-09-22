import uuid
from enum import Enum
from typing import Any, Optional, Type

from gi.repository import Gio, GObject, Gtk, Pango

from ..adapters import AdapterManager, UIInfo
from ..adapters.filesystem import FilesystemAdapter
from ..config import ConfigurationStore, ProviderConfiguration


class AdapterTypeModel(GObject.GObject):
    adapter_type = GObject.Property(type=object)

    def __init__(self, adapter_type: Type):
        GObject.GObject.__init__(self)
        self.adapter_type = adapter_type


class DialogStage(Enum):
    SELECT_ADAPTER = "select"
    CONFIGURE_ADAPTER = "configure"


class ConfigureProviderDialog(Gtk.Dialog):
    _current_index = -1
    stage = DialogStage.SELECT_ADAPTER

    def set_title(self, editing: bool, provider_config: ProviderConfiguration = None):
        if editing:
            assert provider_config is not None
            title = f"Edit {provider_config.name}"
        else:
            title = "Add New Music Source"

        self.header.props.title = title

    def __init__(self, parent: Any, provider_config: Optional[ProviderConfiguration]):
        Gtk.Dialog.__init__(self, transient_for=parent, flags=Gtk.DialogFlags.MODAL)
        self.provider_config = provider_config
        self.editing = provider_config is not None
        self.set_default_size(400, 350)

        # HEADER
        self.header = Gtk.HeaderBar()
        self.set_title(self.editing, provider_config)

        self.cancel_back_button = Gtk.Button(label="Cancel")
        self.cancel_back_button.connect("clicked", self._on_cancel_back_clicked)
        self.header.pack_start(self.cancel_back_button)

        self.next_add_button = Gtk.Button(label="Edit" if self.editing else "Next")
        self.next_add_button.get_style_context().add_class("suggested-action")
        self.next_add_button.connect("clicked", self._on_next_add_clicked)
        self.header.pack_end(self.next_add_button)

        self.set_titlebar(self.header)

        content_area = self.get_content_area()

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        # ADAPTER TYPE OPTIONS
        adapter_type_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.adapter_type_store = Gio.ListStore()
        self.adapter_options_list = Gtk.ListBox(
            name="ground-truth-adapter-options-list", activate_on_single_click=False
        )
        self.adapter_options_list.connect("row-activated", self._on_next_add_clicked)

        def create_row(model: AdapterTypeModel) -> Gtk.ListBoxRow:
            ui_info: UIInfo = model.adapter_type.get_ui_info()
            row = Gtk.ListBoxRow()
            rowbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            rowbox.pack_start(
                Gtk.Image.new_from_icon_name(ui_info.icon_name(), Gtk.IconSize.DND),
                False,
                False,
                5,
            )
            rowbox.add(
                Gtk.Label(
                    label=f"<b>{ui_info.name}</b>\n{ui_info.description}",
                    use_markup=True,
                    margin=8,
                    halign=Gtk.Align.START,
                    ellipsize=Pango.EllipsizeMode.END,
                )
            )

            row.add(rowbox)
            row.show_all()
            return row

        self.adapter_options_list.bind_model(self.adapter_type_store, create_row)

        available_ground_truth_adapters = filter(
            lambda a: a.can_be_ground_truth, AdapterManager.available_adapters
        )
        for adapter_type in sorted(
            available_ground_truth_adapters, key=lambda a: a.get_ui_info().name
        ):
            self.adapter_type_store.append(AdapterTypeModel(adapter_type))

        adapter_type_box.pack_start(self.adapter_options_list, True, True, 10)
        self.stack.add_named(adapter_type_box, "select")

        self.configure_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.stack.add_named(self.configure_box, "configure")

        content_area.pack_start(self.stack, True, True, 0)

        self.show_all()

        if self.editing:
            assert self.provider_config
            for i, adapter_type in enumerate(self.adapter_type_store):
                if (
                    adapter_type.adapter_type
                    == self.provider_config.ground_truth_adapter_type
                ):
                    row = self.adapter_options_list.get_row_at_index(i)
                    self.adapter_options_list.select_row(row)
                    break
            self._name_is_valid = True
            self._on_next_add_clicked()

    def _on_cancel_back_clicked(self, _):
        if self.stage == DialogStage.SELECT_ADAPTER:
            self.close()
        else:
            self.stack.set_visible_child_name("select")
            self.stage = DialogStage.SELECT_ADAPTER
            self.cancel_back_button.set_label("Cancel")
            self.next_add_button.set_label("Next")
            self.next_add_button.set_sensitive(True)

    def _on_next_add_clicked(self, *args):
        if self.stage == DialogStage.SELECT_ADAPTER:
            index = self.adapter_options_list.get_selected_row().get_index()
            if index != self._current_index:
                for c in self.configure_box.get_children():
                    self.configure_box.remove(c)

                name_entry_grid = Gtk.Grid(
                    column_spacing=10,
                    row_spacing=5,
                    margin_left=10,
                    margin_right=10,
                    name="music-source-config-name-entry-grid",
                )
                name_label = Gtk.Label(label="Music Source Name:")
                name_entry_grid.attach(name_label, 0, 0, 1, 1)
                self.name_field = Gtk.Entry(
                    text=self.provider_config.name if self.provider_config else "",
                    hexpand=True,
                )
                self.name_field.connect("changed", self._on_name_change)
                name_entry_grid.attach(self.name_field, 1, 0, 1, 1)
                self.configure_box.add(name_entry_grid)

                self.configure_box.add(Gtk.Separator())

                self.adapter_type = self.adapter_type_store[index].adapter_type
                self.config_store = (
                    self.provider_config.ground_truth_adapter_config
                    if self.provider_config
                    else ConfigurationStore()
                )
                form = self.adapter_type.get_configuration_form(self.config_store)
                form.connect("config-valid-changed", self._on_config_form_valid_changed)
                self.configure_box.pack_start(form, True, True, 0)
                self.configure_box.show_all()
                self._adapter_config_is_valid = False

            self.stack.set_visible_child_name("configure")
            self.stage = DialogStage.CONFIGURE_ADAPTER
            self.cancel_back_button.set_label("Change Type" if self.editing else "Back")
            self.next_add_button.set_label("Edit" if self.editing else "Add")
            self.next_add_button.set_sensitive(
                index == self._current_index and self._adapter_config_is_valid
            )
            self._current_index = index
        else:
            if self.provider_config is None:
                self.provider_config = ProviderConfiguration(
                    str(uuid.uuid4()),
                    self.name_field.get_text(),
                    self.adapter_type,
                    self.config_store,
                )
                if self.adapter_type.can_be_cached:
                    self.provider_config.caching_adapter_type = FilesystemAdapter
                    self.provider_config.caching_adapter_config = ConfigurationStore()
            else:
                self.provider_config.name = self.name_field.get_text()
                self.provider_config.ground_truth_adapter_config = self.config_store

            self.response(Gtk.ResponseType.APPLY)

    _name_is_valid = False
    _adapter_config_is_valid = False

    def _update_add_button_sensitive(self):
        self.next_add_button.set_sensitive(
            self._name_is_valid and self._adapter_config_is_valid
        )

    def _on_name_change(self, entry: Gtk.Entry):
        if entry.get_text():
            self._name_is_valid = True
            entry.get_style_context().remove_class("invalid")
            entry.set_tooltip_markup(None)

            if self.editing:
                assert self.provider_config
                self.provider_config.name = entry.get_text()
                self.set_title(self.editing, self.provider_config)
        else:
            self._name_is_valid = False
            entry.get_style_context().add_class("invalid")
            entry.set_tooltip_markup("This field is required")
        self._update_add_button_sensitive()

    def _on_config_form_valid_changed(self, _, valid: bool):
        self._adapter_config_is_valid = valid
        self._update_add_button_sensitive()
