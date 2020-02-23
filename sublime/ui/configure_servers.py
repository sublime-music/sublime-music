import subprocess
from typing import Any

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GObject, Gtk

from sublime.config import AppConfiguration, ServerConfiguration
from sublime.server import Server
from sublime.ui.common import EditFormDialog, IconButton


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
        ('Play queue sync enabled', 'sync_enabled'),
        ('Do not verify certificate', 'disable_cert_verify'),
    ]

    def __init__(self, *args, **kwargs):
        test_server = Gtk.Button(label='Test Connection to Server')
        test_server.connect('clicked', self.on_test_server_clicked)

        open_in_browser = Gtk.Button(label='Open in Browser')
        open_in_browser.connect('clicked', self.on_open_in_browser_clicked)

        self.extra_buttons = [(test_server, None), (open_in_browser, None)]

        super().__init__(*args, **kwargs)

    def on_test_server_clicked(self, event: Any):
        # Instantiate the server.
        server_address = self.data['server_address'].get_text()
        server = Server(
            name=self.data['name'].get_text(),
            hostname=server_address,
            username=self.data['username'].get_text(),
            password=self.data['password'].get_text(),
            disable_cert_verify=self.data['disable_cert_verify'].get_active(),
        )

        # Try to ping, and show a message box with whether or not it worked.
        try:
            server.ping()
            dialog = Gtk.MessageDialog(
                transient_for=self,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text='Connection to server successful.',
            )
            dialog.format_secondary_markup(
                f'Connection to {server_address} successful.')
        except Exception as err:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text='Connection to server unsuccessful.',
            )
            dialog.format_secondary_markup(
                f'Connection to {server_address} resulted in the following '
                f'error:\n\n{err}')

        dialog.run()
        dialog.destroy()

    def on_open_in_browser_clicked(self, event: Any):
        subprocess.call(['xdg-open', self.data['server_address'].get_text()])


class ConfigureServersDialog(Gtk.Dialog):
    __gsignals__ = {
        'server-list-changed':
        (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (object, )),
        'connected-server-changed':
        (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (object, )),
    }

    def __init__(self, parent: Any, config: AppConfiguration):
        Gtk.Dialog.__init__(
            self,
            title='Configure Servers',
            transient_for=parent,
            flags=0,
            add_buttons=(),
        )

        self.server_configs = config.servers
        self.selected_server_index = config.current_server
        self.set_default_size(500, 300)

        # Flow box to hold the server list and the buttons.
        flowbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Server List
        self.server_list = Gtk.ListBox(activate_on_single_click=False)
        self.server_list.connect(
            'selected-rows-changed', self.server_list_on_selected_rows_changed)
        self.server_list.connect('row-activated', self.on_server_list_activate)
        flowbox.pack_start(self.server_list, True, True, 10)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # Tuples: (button, action function, pack side, requires_selection)
        # Add all of the buttons to the button box.
        self.buttons = [
            (
                IconButton(
                    'document-edit-symbolic',
                    label='Edit...',
                    relief=True,
                ), lambda e: self.on_edit_clicked(False), 'start', True),
            (
                IconButton(
                    'list-add-symbolic',
                    label='Add...',
                    relief=True,
                ), lambda e: self.on_edit_clicked(True), 'start', False),
            (
                IconButton(
                    'list-remove-symbolic',
                    label='Remove',
                    relief=True,
                ), self.on_remove_clicked, 'start', True),
            (
                IconButton(
                    'window-close-symbolic',
                    label='Close',
                    relief=True,
                ), lambda _: self.close(), 'end', False),
            (
                IconButton(
                    'network-transmit-receive-symbolic',
                    label='Connect',
                    relief=True,
                ), self.on_connect_clicked, 'end', True),
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
        for i, config in enumerate(self.server_configs):
            box = Gtk.Box()
            image = Gtk.Image(margin=5)
            if i == self.selected_server_index:
                image.set_from_icon_name(
                    'network-transmit-receive-symbolic',
                    Gtk.IconSize.SMALL_TOOLBAR,
                )

            box.add(image)

            server_name_label = Gtk.Label(label=config.name)
            server_name_label.set_halign(Gtk.Align.START)
            box.add(server_name_label)
            self.server_list.add(box)

        # Show them, and select the current server.
        self.show_all()
        if (self.selected_server_index is not None
                and self.selected_server_index >= 0):
            self.server_list.select_row(
                self.server_list.get_row_at_index(self.selected_server_index))

    def on_remove_clicked(self, event: Any):
        selected = self.server_list.get_selected_row()
        if selected:
            del self.server_configs[selected.get_index()]
            self.refresh_server_list()
            self.emit('server-list-changed', self.server_configs)

    def on_edit_clicked(self, add: bool):
        if add:
            dialog = EditServerDialog(self)
        else:
            selected_index = self.server_list.get_selected_row().get_index()
            dialog = EditServerDialog(
                self, self.server_configs[selected_index])

        result = dialog.run()
        if result == Gtk.ResponseType.OK:
            # Create a new server configuration to use.
            new_config = ServerConfiguration(
                name=dialog.data['name'].get_text(),
                server_address=dialog.data['server_address'].get_text(),
                local_network_address=dialog.data['local_network_address']
                .get_text(),
                local_network_ssid=dialog.data['local_network_ssid'].get_text(
                ),
                username=dialog.data['username'].get_text(),
                password=dialog.data['password'].get_text(),
                sync_enabled=dialog.data['sync_enabled'].get_active(),
                disable_cert_verify=dialog.data['disable_cert_verify']
                .get_active(),
            )

            if add:
                self.server_configs.append(new_config)
            else:
                self.server_configs[selected_index] = new_config

            self.refresh_server_list()
            self.emit('server-list-changed', self.server_configs)

        dialog.destroy()

    def on_server_list_activate(self, *args):
        self.on_connect_clicked(None)

    def on_connect_clicked(self, event: Any):
        selected_index = self.server_list.get_selected_row().get_index()
        self.emit('connected-server-changed', selected_index)
        self.close()

    def server_list_on_selected_rows_changed(self, event: Any):
        # Update the state of the buttons depending on whether or not a row is
        # selected in the server list.
        has_selection = self.server_list.get_selected_row()

        for button, *_, requires_selection in self.buttons:
            button.set_sensitive(not requires_selection or has_selection)
