import gi
import subprocess
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject

from libremsonic.server import Server
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

        # Create the two columns for the labels and corresponding entry fields.
        self.set_default_size(450, 250)
        content_area = self.get_content_area()
        flowbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        flowbox.pack_start(label_box, False, True, 10)
        flowbox.pack_start(entry_box, True, True, 10)

        self.data = {}

        # Create all of the text entry fields for the server configuration.
        text_fields = [
            ('Name', existing_config.name, False),
            ('Server address', existing_config.server_address, False),
            ('Local network address', existing_config.local_network_address,
             False),
            ('Local network SSID', existing_config.local_network_ssid, False),
            ('Username', existing_config.username, False),
            ('Password', existing_config.password, True),
        ]
        for label, value, is_password in text_fields:
            entry_label = Gtk.Label(label + ':')
            entry_label.set_halign(Gtk.Align.START)
            label_box.pack_start(entry_label, True, True, 0)

            entry = Gtk.Entry(text=value)
            if is_password:
                entry.set_visibility(False)
            entry_box.pack_start(entry, True, True, 0)
            self.data[label] = entry

        # Create all of the check box fields for the server configuration.
        boolean_fields = [
            ('Browse by tags', existing_config.browse_by_tags),
            ('Sync enabled', existing_config.sync_enabled),
        ]
        for label, value in boolean_fields:
            entry_label = Gtk.Label(label + ':')
            entry_label.set_halign(Gtk.Align.START)
            label_box.pack_start(entry_label, True, True, 0)

            checkbox = Gtk.CheckButton(active=value)
            entry_box.pack_start(checkbox, True, True, 5)
            self.data[label] = checkbox

        content_area.pack_start(flowbox, True, True, 10)

        # Create a box for buttons.
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        test_server = Gtk.Button('Test Connection to Server')
        test_server.connect('clicked', self.on_test_server_clicked)
        button_box.pack_start(test_server, False, True, 5)

        open_in_browser = Gtk.Button('Open in Browser')
        open_in_browser.connect('clicked', self.on_open_in_browser_clicked)
        button_box.pack_start(open_in_browser, False, True, 5)

        content_area.pack_start(button_box, True, True, 10)

        self.show_all()

    def on_test_server_clicked(self, event):
        server = Server(
            self.data['Name'].get_text(),
            self.data['Server address'].get_text(),
            self.data['Username'].get_text(),
            self.data['Password'].get_text(),
        )
        server.ping()

    def on_open_in_browser_clicked(self, event):
        subprocess.call(['xdg-open', self.data['Server address'].get_text()])


class ConfigureServersDialog(Gtk.Dialog):
    __gsignals__ = {
        'server-list-changed': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE,
                                (object, )),
        'connected-server-changed': (GObject.SIGNAL_RUN_FIRST,
                                     GObject.TYPE_NONE, (object, )),
    }

    def __init__(self, parent, config):
        Gtk.Dialog.__init__(self, 'Connect to Server', parent, 0, ())

        self.server_configs = config.servers
        self.selected_server_index = config.current_server
        self.set_default_size(450, 300)

        flowbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.server_list = Gtk.ListBox()
        self.server_list.connect('selected-rows-changed',
                                 self.server_list_on_selected_rows_changed)

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
            (Gtk.Button('Connect'), self.on_connect_clicked, 'end', False),
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
        self.refresh_server_list()
        self.server_list_on_selected_rows_changed(None)

    def refresh_server_list(self):
        for el in self.server_list:
            self.server_list.remove(el)

        for config in self.server_configs:
            row = Gtk.ListBoxRow()
            server_name_label = Gtk.Label(config.name)
            server_name_label.set_halign(Gtk.Align.START)
            row.add(server_name_label)
            self.server_list.add(row)

        self.show_all()
        if self.selected_server_index is not None and self.selected_server_index >= 0:
            self.server_list.select_row(
                self.server_list.get_row_at_index(self.selected_server_index))

    def on_remove_clicked(self, event):
        selected = self.server_list.get_selected_row()
        if selected:
            del self.server_configs[selected.get_index()]
            self.refresh_server_list()
            self.emit('server-list-changed', self.server_configs)

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
                browse_by_tags=dialog.data['Browse by tags'].get_active(),
                sync_enabled=dialog.data['Sync enabled'].get_active(),
            )

            if add:
                self.server_configs.append(new_config)
            else:
                self.server_configs[selected_index] = new_config

            self.emit('server-list-changed', self.server_configs)

        dialog.destroy()

    def on_connect_clicked(self, event):
        selected_index = self.server_list.get_selected_row().get_index()
        self.emit('connected-server-changed', selected_index)
        self.close()

    def server_list_on_selected_rows_changed(self, event):
        has_selection = self.server_list.get_selected_row()

        for button, *_, requires_selection in self.buttons:
            button.set_sensitive(not requires_selection or has_selection)
