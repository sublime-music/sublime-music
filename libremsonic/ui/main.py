import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk

from .albums import AlbumsPanel
from .player_controls import PlayerControls
from libremsonic.config import AppConfiguration


class MainWindow(Gtk.ApplicationWindow):
    """Defines the main window for LibremSonic."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(1024, 768)

        self.panels = {
            'Albums': AlbumsPanel(),
            'Artists': Gtk.Label('Artists'),
            'Playlists': Gtk.Label('Playlists'),
            'More': Gtk.Label('More'),
        }

        # Create the stack
        stack = self.create_stack(**self.panels)
        stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        self.titlebar = self.create_headerbar(stack)
        self.set_titlebar(self.titlebar)

        self.player_controls = PlayerControls()

        flowbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        flowbox.pack_start(stack, True, True, 0)
        flowbox.pack_start(self.player_controls, False, True, 0)
        self.add(flowbox)

    def update(self, config: AppConfiguration):
        # Update the Connected to label on the popup menu.
        if config.current_server >= 0:
            server_name = config.servers[config.current_server].name
            self.connected_to_label.set_markup(f'Connected to {server_name}')
        else:
            self.connected_to_label.set_markup(
                f'<span style="italic">Not Connected to a Server</span>')

        print(self.panels)

    def create_stack(self, **kwargs):
        stack = Gtk.Stack()
        for name, child in kwargs.items():
            stack.add_titled(child, name.lower(), name)
        return stack

    def create_headerbar(self, stack):
        """
        Configure the header bar for the window.
        """
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.props.title = 'LibremSonic'

        # Search
        search = Gtk.SearchEntry()
        header.pack_start(search)

        # Stack switcher
        switcher = Gtk.StackSwitcher(stack=stack)
        header.set_custom_title(switcher)

        # Menu button
        button = Gtk.MenuButton()
        button.set_use_popover(True)
        button.set_popover(self.create_menu())
        button.connect('clicked', self.on_menu_click)

        icon = Gio.ThemedIcon(name="open-menu-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        button.add(image)

        header.pack_end(button)

        return header

    def create_menu(self):
        self.menu = Gtk.PopoverMenu()

        self.connected_to_label = Gtk.Label()
        self.connected_to_label.set_markup(
            f'<span style="italic">Not Connected to a Server</span>')
        self.connected_to_label.set_margin_left(10)
        self.connected_to_label.set_margin_right(10)

        menu_items = [
            (None, self.connected_to_label),
            ('app.configure_servers', Gtk.ModelButton('Connect to Server')),
        ]

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for name, item in menu_items:
            if name:
                item.set_action_name(name)
            vbox.pack_start(item, False, True, 10)
        self.menu.add(vbox)

        return self.menu

    # ========== Event Listeners ==========
    def on_menu_click(self, button):
        self.menu.set_relative_to(button)
        self.menu.show_all()
        self.menu.popup()
