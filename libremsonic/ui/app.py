import os

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, GLib

from libremsonic.config import get_config, save_config

from .main import MainWindow
from .configure_servers import ConfigureServersDialog


class LibremsonicApp(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="com.sumnerevans.libremsonic",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            **kwargs,
        )
        self.window = None
        self.config_file = None
        self.config = None

        # Specify Command Line Options
        self.add_main_option(
            'config', ord('c'), GLib.OptionFlags.NONE, GLib.OptionArg.FILENAME,
            'Specify a configuration file. Defaults to ~/.config/libremsonic/config.json',
            None)

    # Handle command line option parsing.
    def do_command_line(self, command_line):
        options = command_line.get_options_dict()

        # Config File
        self.config_file = options.lookup_value('config')
        if self.config_file:
            self.config_file = self.config_file.get_bytestring().decode(
                'utf-8')
        else:
            # Default to ~/.config/libremsonic.
            config_folder = (os.environ.get('XDG_CONFIG_HOME')
                             or os.environ.get('APPDATA') or os.path.join(
                                 os.environ.get('HOME'), '.config'))
            config_folder = os.path.join(config_folder, 'libremsonic')
            self.config_file = os.path.join(config_folder, 'config.yaml')

        # Have to do this or else the application doesn't work. Not entirely
        # sure why, but C-bindings...
        self.activate()
        return 0

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # Add action for configuring servers
        action = Gio.SimpleAction.new('configure_servers', None)
        action.connect('activate', self.on_configure_servers)
        self.add_action(action)

    def do_activate(self):
        # We only allow a single window and raise any existing ones
        if not self.window:
            # Windows are associated with the application
            # when the last one is closed the application shuts down
            self.window = MainWindow(application=self, title="LibremSonic")

        self.window.show_all()
        self.window.present()

        # Load the configuration and update the UI with the curent server, if
        # it exists. If there is no current server, show the dialog to select a
        # server.
        self.load_settings()

        if self.config.current_server is None:
            self.show_configure_servers_dialog()
        else:
            self.on_connected_server_changed(None, self.config.current_server)

    def on_configure_servers(self, action, param):
        self.show_configure_servers_dialog()

    def on_server_list_changed(self, action, servers):
        self.config.servers = servers
        self.save_settings()

    def on_connected_server_changed(self, action, current_server):
        self.config.current_server = current_server
        self.save_settings()

        # Update the window according to the new server configuration.
        self.window.update(self.config)

    def show_configure_servers_dialog(self):
        """Show the Connect to Server dialog."""
        dialog = ConfigureServersDialog(self.window, self.config)
        dialog.connect('server-list-changed', self.on_server_list_changed)
        dialog.connect('connected-server-changed',
                       self.on_connected_server_changed)
        dialog.run()
        dialog.destroy()

    def load_settings(self):
        self.config = get_config(self.config_file)

    def save_settings(self):
        save_config(self.config, self.config_file)
