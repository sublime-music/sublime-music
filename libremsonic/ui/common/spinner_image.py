import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


class SpinnerImage(Gtk.Overlay):
    def __init__(
            self,
            loading=True,
            image_name=None,
            spinner_name=None,
            **kwargs,
    ):
        Gtk.Overlay.__init__(self)

        self.image = Gtk.Image(name=image_name, **kwargs)
        self.add(self.image)

        self.spinner = Gtk.Spinner(
            name=spinner_name,
            active=loading,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        self.add_overlay(self.spinner)

    def set_from_file(self, *args, **kwargs):
        self.image.set_from_file(*args, **kwargs)

    def set_loading(self, loading_status):
        if loading_status:
            self.spinner.start()
            self.spinner.show()
        else:
            self.spinner.stop()
            self.spinner.hide()
