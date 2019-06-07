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

        self.add_main_option(
            'config', ord('c'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
            'Specify a configuration file. Defaults to ~/.config/libremsonic/config.json',
            None)

        # TODO load this from the config file
        self.config = None

    def do_command_line(self, command_line):
        options = command_line.get_options_dict().end().unpack()
        print(options)

        self.activate()
        return 0

    def do_startup(self):
        Gtk.Application.do_startup(self)

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

        self.load_settings()

        if self.config.current_server is None:
            self.show_configure_servers_dialog()

        print('current config', self.config)

    def on_configure_servers(self, action, param):
        self.show_configure_servers_dialog()

    def on_server_list_changed(self, action, params):
        server_config, *_ = params

        self.save_settings()

    def show_configure_servers_dialog(self):
        dialog = ConfigureServersDialog(self.window, self.config.servers)
        dialog.connect('server-list-changed', self.on_server_list_changed)
        dialog.run()
        dialog.destroy()

    def load_settings(self):
        self.config = get_config(os.path.expanduser('~/tmp/test.json'))

    def save_settings(self):
        save_config(self.config, os.path.expanduser('~/tmp/test.json'))
