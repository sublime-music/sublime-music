from typing import Optional

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
        """An image with a loading overlay."""
        Gtk.Overlay.__init__(self)
        self.image_size = image_size
        self.filename: Optional[str] = None

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
        """Set the image to the given filename."""
        if filename == "":
            filename = None
        self.filename = filename
        if self.image_size is not None and filename:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                filename, self.image_size, self.image_size, True
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

    def set_image_size(self, size: int):
        self.image_size = size
        self.set_from_file(self.filename)
