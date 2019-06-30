import gi
import sys

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, GObject

from libremsonic.state_manager import ApplicationState


class MorePanel(Gtk.ScrolledWindow):
    __gsignals__ = {
        'song-clicked': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                         (str, object)),
    }

    def __init__(self):
        Gtk.ScrolledWindow.__init__(self)
        self.child = MoreGrid()
        self.add(self.child)

    def update(self, state: ApplicationState):
        self.child.update(state)


class MoreGrid(Gtk.FlowBox):
    """Defines the albums panel."""

    def __init__(self):
        Gtk.FlowBox.__init__(
            self,
            vexpand=True,
            hexpand=True,
            row_spacing=12,
            column_spacing=12,
            margin_top=12,
            margin_bottom=12,
            homogeneous=True,
            valign=Gtk.Align.START,
            halign=Gtk.Align.CENTER,
            selection_mode=Gtk.SelectionMode.NONE,
        )

    def update(self, state: ApplicationState):
        pass
