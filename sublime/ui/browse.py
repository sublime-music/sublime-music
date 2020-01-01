import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, Pango, GLib, Gio


class BrowsePanel(Gtk.Label):
    """Defines the arist panel."""

    __gsignals__ = {
        'song-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        'refresh-window': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    def __init__(self):
        super().__init__(label='ohea')
