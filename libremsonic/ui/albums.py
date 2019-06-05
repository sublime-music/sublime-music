import gi
import sys

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk


class AlbumsPanel(Gtk.Box):
    """Defines the albums panel."""

    def __init__(self):
        Gtk.Container.__init__(self)

        albums = Gtk.Label('Albums')

        self.add(albums)
