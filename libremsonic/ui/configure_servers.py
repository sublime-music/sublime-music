import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from libremsonic.config import ServerConfiguration


class EditServerDialog(Gtk.Dialog):
    def __init__(self, parent, existing_config=None):
        editing = existing_config != None
        Gtk.Dialog.__init__(
            self,
            f'Edit {existing_config.name}' if editing else 'Add New Server',
            parent, 0, (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                        Gtk.STOCK_EDIT if editing else Gtk.STOCK_ADD,
                        Gtk.ResponseType.OK))

        if not existing_config:
            existing_config = ServerConfiguration()

        self.set_default_size(400, 250)
        content_area = self.get_content_area()
        flowbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        flowbox.pack_start(label_box, False, True, 10)
        flowbox.pack_start(entry_box, True, True, 10)

        self.data = {}

        text_fields = [
            ('Name', existing_config.name),
            ('Server address', existing_config.server_address),
            ('Local network address', existing_config.local_network_address),
            ('Local network SSID', existing_config.local_network_ssid),
            ('Username', existing_config.username),
            ('Password', existing_config.password),
        ]
        for label, value in text_fields:
            entry_label = Gtk.Label(label + ':')
            entry_label.set_halign(Gtk.Align.START)
            label_box.pack_start(entry_label, True, True, 0)

            entry = Gtk.Entry(text=value)
            entry_box.pack_start(entry, True, True, 0)
            self.data[label] = entry

        content_area.pack_start(flowbox, True, True, 10)
        self.show_all()


class ConfigureServersDialog(Gtk.Dialog):
    def __init__(self, parent):
        Gtk.Dialog.__init__(self, 'Configure Servers', parent, 0, ())

        # TODO: DEBUG DATA
        self.server_configs = [
            ServerConfiguration(name='ohea'),
            ServerConfiguration()
        ]

        self.set_default_size(400, 250)

        flowbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.server_list = Gtk.ListBox()
        self.server_list.connect('selected-rows-changed',
                                 self.server_list_on_selected_rows_changed)
        self.refresh_server_list()

        flowbox.pack_start(self.server_list, True, True, 10)

        # Right Side
        button_array = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # Tuples: (button, action function, pack side, requires_selection)
        self.buttons = [
            # TODO get good icons for these
            (Gtk.Button('Edit...'), lambda e: self.on_edit_clicked(e, False),
             'start', True),
            (Gtk.Button('Add...'), lambda e: self.on_edit_clicked(e, True),
             'start', False),
            (Gtk.Button('Remove'), self.on_remove_clicked, 'start', True),
            (Gtk.Button('Close'), lambda _: self.close(), 'end', False),
        ]
        for button_cfg in self.buttons:
            btn, action, pack_end, requires_selection = button_cfg

            if pack_end == 'end':
                button_array.pack_end(btn, False, True, 5)
            else:
                button_array.pack_start(btn, False, True, 5)

            btn.connect('clicked', action)

        flowbox.pack_end(button_array, False, False, 0)

        content_area = self.get_content_area()
        content_area.pack_start(flowbox, True, True, 10)
        self.show_all()

    def refresh_server_list(self):
        for el in self.server_list:
            self.server_list.remove(el)

        for config in self.server_configs:
            row = Gtk.ListBoxRow()
            server_name_label = Gtk.Label(config.name)
            server_name_label.set_halign(Gtk.Align.START)
            row.add(server_name_label)
            self.server_list.add(row)

        print(self.server_list, self.server_configs)
        self.show_all()

    def on_remove_clicked(self, event):
        selected = self.server_list.get_selected_row()
        if selected:
            del self.server_configs[selected.get_index()]
            self.refresh_server_list()

    def on_edit_clicked(self, event, add):
        if add:
            dialog = EditServerDialog(self)
        else:
            selected_index = self.server_list.get_selected_row().get_index()
            dialog = EditServerDialog(self,
                                      self.server_configs[selected_index])

        result = dialog.run()
        if result == Gtk.ResponseType.OK:
            new_config = ServerConfiguration(
                name=dialog.data['Name'].get_text(),
                server_address=dialog.data['Server address'].get_text(),
                local_network_address=dialog.data['Local network address'].
                get_text(),
                local_network_ssid=dialog.data['Local network SSID'].get_text(
                ),
                username=dialog.data['Username'].get_text(),
                password=dialog.data['Password'].get_text(),
            )

            if add:
                self.server_configs.append(new_config)
            else:
                self.server_configs[selected_index] = new_config

            print([x.name for x in self.server_configs])

            self.refresh_server_list()
        dialog.destroy()

    def server_list_on_selected_rows_changed(self, event):
        has_selection = self.server_list.get_selected_row()

        for button, *_, requires_selection in self.buttons:
            button.set_sensitive(not requires_selection or has_selection)
