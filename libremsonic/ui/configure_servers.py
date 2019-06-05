import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


class ConfigureServersDialog(Gtk.Dialog):
    def __init__(self, parent):
        Gtk.Dialog.__init__(self, 'Configure Servers', parent, 0,
                            ('Done', Gtk.ResponseType.NONE))

        self.set_default_size(400, 400)
        label = Gtk.Label('ohea')

        box = self.get_content_area()
        box.add(label)
        self.show_all()
