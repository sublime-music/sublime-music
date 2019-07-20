import gi
import subprocess
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject

from libremsonic.server import Server
from libremsonic.config import ServerConfiguration
from libremsonic.ui.common import EditFormDialog


class EditServerDialog(EditFormDialog):
    entity_name: str = 'Server'
    initial_size = (450, 250)
    text_fields = [
        ('Name', 'name', False),
        ('Server address', 'server_address', False),
        ('Local network address', 'local_network_address', False),
        ('Local network SSID', 'local_network_ssid', False),
        ('Username', 'username', False),
        ('Password', 'password', True),
    ]
    boolean_fields = [
        ('Browse by tags', 'browse_by_tags'),
        ('Sync enabled', 'sync_enabled'),
    ]

    def __init__(self, *args, **kwargs):
        test_server = Gtk.Button('Test Connection to Server')
        test_server.connect('clicked', self.on_test_server_clicked)

        open_in_browser = Gtk.Button('Open in Browser')
        open_in_browser.connect('clicked', self.on_open_in_browser_clicked)

        self.extra_buttons = [test_server, open_in_browser]

        super().__init__(*args, **kwargs)

    def on_test_server_clicked(self, event):
        # Instantiate the server.
        server = Server(
            self.data['Name'].get_text(),
            self.data['Server address'].get_text(),
            self.data['Username'].get_text(),
            self.data['Password'].get_text(),
        )

        # Try to ping, and show a message box with whether or not it worked.
        try:
            server.ping()
            dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.INFO,
                                       Gtk.ButtonsType.OK,
                                       'Connection to server successful.')
            dialog.format_secondary_markup(
                f"Connection to {self.data['Server address'].get_text()} successful."
            )
        except Exception as err:
            dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR,
                                       Gtk.ButtonsType.OK,
                                       'Connection to server unsuccessful.')
            dialog.format_secondary_markup(
                f"Connection to {self.data['Server address'].get_text()} resulted in the following error:\n\n{err}"
            )

        dialog.run()
        dialog.destroy()

    def on_open_in_browser_clicked(self, event):
        subprocess.call(['xdg-open', self.data['Server address'].get_text()])


class ConfigureServersDialog(Gtk.Dialog):
    __gsignals__ = {
        'server-list-changed': (GObject.SignalFlags.RUN_FIRST,
                                GObject.TYPE_NONE, (object, )),
        'connected-server-changed': (GObject.SignalFlags.RUN_FIRST,
                                     GObject.TYPE_NONE, (object, )),
    }

    def __init__(self, parent, config):
        Gtk.Dialog.__init__(self, 'Connect to Server', parent, 0, ())

        self.server_configs = config.servers
        self.selected_server_index = config.current_server
        self.set_default_size(450, 300)

        # Flow box to hold the server list and the buttons.
        flowbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Server List
        self.server_list = Gtk.ListBox()
        self.server_list.connect('selected-rows-changed',
                                 self.server_list_on_selected_rows_changed)
        flowbox.pack_start(self.server_list, True, True, 10)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # Tuples: (button, action function, pack side, requires_selection)
        # Add all of the buttons to the button box.
        self.buttons = [
            # TODO get good icons for these
            (Gtk.Button(label='Edit...'),
             lambda e: self.on_edit_clicked(e, False), 'start', True),
            (Gtk.Button(label='Add...'),
             lambda e: self.on_edit_clicked(e, True), 'start', False),
            (Gtk.Button(label='Remove'), self.on_remove_clicked, 'start',
             True),
            (Gtk.Button(label='Close'), lambda _: self.close(), 'end', False),
            (Gtk.Button(label='Connect'), self.on_connect_clicked, 'end',
             True),
        ]
        for button_cfg in self.buttons:
            btn, action, pack_end, requires_selection = button_cfg

            if pack_end == 'end':
                button_box.pack_end(btn, False, True, 5)
            else:
                button_box.pack_start(btn, False, True, 5)

            btn.connect('clicked', action)

        flowbox.pack_end(button_box, False, False, 0)

        # Add the flowbox to the dialog and show the dialog.
        content_area = self.get_content_area()
        content_area.pack_start(flowbox, True, True, 10)

        self.show_all()
        self.refresh_server_list()
        self.server_list_on_selected_rows_changed(None)

    def refresh_server_list(self):
        # Clear out the list.
        for el in self.server_list:
            self.server_list.remove(el)

        # Add all of the rows for each of the servers.
        for config in self.server_configs:
            row = Gtk.ListBoxRow()
            server_name_label = Gtk.Label(label=config.name)
            server_name_label.set_halign(Gtk.Align.START)
            row.add(server_name_label)
            self.server_list.add(row)

        # Show them, and select the current server.
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
            # Create a new server configuration to use.
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

            self.refresh_server_list()
            self.emit('server-list-changed', self.server_configs)

        dialog.destroy()

    def on_connect_clicked(self, event):
        selected_index = self.server_list.get_selected_row().get_index()
        self.emit('connected-server-changed', selected_index)
        self.close()

    def server_list_on_selected_rows_changed(self, event):
        # Update the state of the buttons depending on whether or not a row is
        # selected in the server list.
        has_selection = self.server_list.get_selected_row()

        for button, *_, requires_selection in self.buttons:
            button.set_sensitive(not requires_selection or has_selection)
