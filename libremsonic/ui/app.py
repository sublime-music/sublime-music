import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk

from .main import MainWindow
from .configure_servers import ConfigureServersDialog


class LibremsonicApp(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="com.sumnerevans.libremsonic",
            **kwargs,
        )
        self.window = None

        # TODO load this from the config file
        self.current_server = None

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

        if not self.current_server:
            self.show_configure_servers_dialog()

    def on_configure_servers(self, action, param):
        self.show_configure_servers_dialog()

    def show_configure_servers_dialog(self):
        dialog = ConfigureServersDialog(self.window)
        dialog.run()
        dialog.destroy()
