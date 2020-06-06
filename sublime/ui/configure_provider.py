from typing import Any, Optional, Type

from gi.repository import Gio, GLib, GObject, Gtk, Pango

from sublime.adapters import Adapter, AdapterManager, UIInfo
from sublime.config import ProviderConfiguration


class AdapterTypeModel(GObject.GObject):
    adapter_type = GObject.Property(type=object)

    def __init__(self, adapter_type: Type):
        GObject.GObject.__init__(self)
        self.adapter_type = adapter_type


class ConfigureProviderDialog(Gtk.Dialog):
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

    def __init__(self, parent: Any, config: Optional[ProviderConfiguration]):
        title = "Add New Music Source" if not config else "Edit {config.name}"
        Gtk.Dialog.__init__(
            self,
            title=title,
            transient_for=parent,
            flags=Gtk.DialogFlags.MODAL,
            add_buttons=(),
        )
        self.set_default_size(400, 500)

        # HEADER
        header = Gtk.HeaderBar()
        header.props.title = title

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda *a: self.close())
        header.pack_start(cancel_button)

        next_button = Gtk.Button(label="Next")
        next_button.connect("clicked", self._on_next_clicked)
        header.pack_end(next_button)

        self.set_titlebar(header)

        content_area = self.get_content_area()

        # ADAPTER TYPE OPTIONS
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

        content_area.pack_start(self.adapter_options_list, True, True, 10)

        self.show_all()

    def _on_next_clicked(self, _):
        index = self.adapter_options_list.get_selected_row().get_index()
        adapter_type = self.adapter_type_store[index].adapter_type
        print(adapter_type)
