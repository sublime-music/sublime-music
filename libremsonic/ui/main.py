import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk

from .albums import AlbumsPanel


class MainWindow(Gtk.ApplicationWindow):
    """Defines the main window for LibremSonic."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(400, 200)

        artists = Gtk.Label('Artists')
        playlists = Gtk.Label('Playlists')
        more = Gtk.Label('More')

        # Create the stack
        stack = self.create_stack(
            Albums=AlbumsPanel(),
            Artists=artists,
            Playlists=playlists,
            More=more,
        )
        stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        titlebar = self.create_headerbar(stack)
        self.set_titlebar(titlebar)
        self.add(stack)

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

        menu_items = [
            ('app.configure_servers', Gtk.ModelButton('Configure Servers')),
        ]

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for name, item in menu_items:
            item.set_action_name(name)
            vbox.pack_start(item, False, True, 10)
        self.menu.add(vbox)

        return self.menu

    # ========== Event Listeners ==========
    def on_menu_click(self, button):
        self.menu.set_relative_to(button)
        self.menu.show_all()
        self.menu.popup()
