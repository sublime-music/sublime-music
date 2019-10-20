import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


class IconButton(Gtk.Button):
    def __init__(
            self,
            icon_name,
            relief=False,
            icon_size=Gtk.IconSize.BUTTON,
            label=None,
            **kwargs,
    ):
        Gtk.Button.__init__(self, **kwargs)
        self.icon_size = icon_size
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, name='icon-button-box')

        self.image = Gtk.Image()
        self.image.set_from_icon_name(icon_name, self.icon_size)
        box.add(self.image)

        if label is not None:
            box.add(Gtk.Label(label=label))

        if not relief:
            self.props.relief = Gtk.ReliefStyle.NONE

        self.add(box)

    def set_icon(self, icon_name):
        self.image.set_from_icon_name(icon_name, self.icon_size)
