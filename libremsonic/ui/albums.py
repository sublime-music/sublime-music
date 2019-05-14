import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk


class AlbumsPanel(Gtk.Box):
    """Defines the albums panel."""
    def __init__(self):
        Gtk.Container.__init__(self)

        albums = Gtk.Label('Albums')

        self.add(albums)

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
