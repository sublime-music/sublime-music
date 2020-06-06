from enum import Enum
from typing import Any, Optional, Type

from gi.repository import Gio, GLib, GObject, Gtk, Pango

from sublime.adapters import Adapter, AdapterManager, UIInfo
from sublime.config import ConfigurationStore, ProviderConfiguration


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

    __gsignals__ = {
        "server-list-changed": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object,),
        ),
        "connected-server-changed": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object,),
        ),
    }

    def __init__(self, parent: Any, provider_config: Optional[ProviderConfiguration]):
        title = (
            "Add New Music Source"
            if not provider_config
            else "Edit {provider_config.name}"
        )
        Gtk.Dialog.__init__(
            self,
            title=title,
            transient_for=parent,
            flags=Gtk.DialogFlags.MODAL,
            add_buttons=(),
        )
        # TODO esc should prompt or go back depending on the page
        self.provider_config = provider_config
        self.set_default_size(400, 500)

        # HEADER
        header = Gtk.HeaderBar()
        header.props.title = title

        self.cancel_back_button = Gtk.Button(label="Cancel")
        self.cancel_back_button.connect("clicked", self._on_cancel_back_clicked)
        header.pack_start(self.cancel_back_button)

        self.next_add_button = Gtk.Button(label="Next")
        self.next_add_button.connect("clicked", self._on_next_add_clicked)
        header.pack_end(self.next_add_button)

        self.set_titlebar(header)

        content_area = self.get_content_area()

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        # ADAPTER TYPE OPTIONS
        adapter_type_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.adapter_type_store = Gio.ListStore()
        self.adapter_options_list = Gtk.ListBox(
            name="ground-truth-adapter-options-list"
        )

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
        # TODO
        available_ground_truth_adapters = AdapterManager.available_adapters
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

    def _on_cancel_back_clicked(self, _):
        if self.stage == DialogStage.SELECT_ADAPTER:
            self.close()
        else:
            self.stage = DialogStage.SELECT_ADAPTER
            self.stack.set_visible_child_name("select")
            self.cancel_back_button.set_label("Cancel")
            self.next_add_button.set_label("Next")

    def _on_next_add_clicked(self, _):
        if self.stage == DialogStage.SELECT_ADAPTER:
            self.stage = DialogStage.CONFIGURE_ADAPTER
            self.cancel_back_button.set_label("Back")
            self.next_add_button.set_label("Add")
            # TODO make the next button the primary action

            index = self.adapter_options_list.get_selected_row().get_index()
            if index != self._current_index:
                for c in self.configure_box.get_children():
                    self.configure_box.remove(c)

                adapter_type = self.adapter_type_store[index].adapter_type
                config_store = (
                    self.provider_config.ground_truth_adapter_config
                    if self.provider_config
                    else ConfigurationStore()
                )
                self.configure_box.pack_start(
                    adapter_type.get_configuration_form(config_store), True, True, 0,
                )
                self.configure_box.show_all()

            self.stack.set_visible_child_name("configure")
        else:
            print("ADD")
