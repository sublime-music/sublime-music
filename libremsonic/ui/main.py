import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk


class MainWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="LibremSonic")
        self.set_default_size(400, 200)

        albums = Gtk.Label('Albums')
        artists = Gtk.Label('Artists')
        playlists = Gtk.Label('Playlists')
        more = Gtk.Label('More')

        # Create the stack
        stack = self.create_stack(
            Albums=albums,
            Artists=artists,
            Playlists=playlists,
            More=more,
        )
        stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        self.set_titlebar(self.create_headerbar(stack))
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
        icon = Gio.ThemedIcon(name="open-menu-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        button.add(image)
        header.pack_end(button)

        return header
