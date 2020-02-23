from typing import Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GdkPixbuf, Gtk


class SpinnerImage(Gtk.Overlay):
    def __init__(
        self,
        loading: bool = True,
        image_name: str = None,
        spinner_name: str = None,
        image_size: int = None,
        **kwargs,
    ):
        Gtk.Overlay.__init__(self)
        self.image_size = image_size

        self.image = Gtk.Image(name=image_name, **kwargs)
        self.add(self.image)

        self.spinner = Gtk.Spinner(
            name=spinner_name,
            active=loading,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        self.add_overlay(self.spinner)

    def set_from_file(self, filename: Optional[str]):
        if filename == '':
            filename = None
        if self.image_size is not None and filename:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                filename,
                self.image_size,
                self.image_size,
                True,
            )
            self.image.set_from_pixbuf(pixbuf)
        else:
            self.image.set_from_file(filename)

    def set_loading(self, loading_status: bool):
        if loading_status:
            self.spinner.start()
            self.spinner.show()
        else:
            self.spinner.stop()
            self.spinner.hide()
