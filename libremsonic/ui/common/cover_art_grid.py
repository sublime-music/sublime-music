from concurrent.futures import Future
from typing import Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk, GObject, Gio, Pango

from libremsonic.state_manager import ApplicationState
from .spinner_image import SpinnerImage


class CoverArtGrid(Gtk.ScrolledWindow):
    """Defines a grid with cover art."""
    __gsignals__ = {
        'item-clicked': (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (object, ),
        )
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grid = Gtk.FlowBox(
            vexpand=True,
            hexpand=True,
            row_spacing=5,
            column_spacing=5,
            margin_top=12,
            margin_bottom=12,
            homogeneous=True,
            valign=Gtk.Align.START,
            halign=Gtk.Align.CENTER,
            selection_mode=Gtk.SelectionMode.BROWSE,
        )
        self.grid.connect('child-activated', self.on_child_activated)

        self.model = Gio.ListStore()
        self.grid.bind_model(self.model, self.create_widget)
        self.add(self.grid)

    def update(self, state: ApplicationState = None):
        self.update_grid()

    def update_grid(self):
        def start_loading():
            print('set loading')

        def stop_loading():
            print('stop loading')

        def future_done(f):
            try:
                result = f.result()
            except Exception as e:
                print('fail', e)
                return

            self.model.remove_all()
            for el in result:
                self.model.append(self.create_model_from_element(el))

            stop_loading()

        future = self.get_model_list_future(before_download=start_loading)
        future.add_done_callback(lambda f: GLib.idle_add(future_done, f))

    def create_widget(self, item):
        widget_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Cover art image
        artwork = SpinnerImage(
            image_name='grid-artwork',
            spinner_name='grid-artwork-spinner',
        )
        widget_box.pack_start(artwork, False, False, 0)

        def make_label(text, name):
            return Gtk.Label(
                name=name,
                label=text,
                tooltip_text=text,
                ellipsize=Pango.EllipsizeMode.END,
                max_width_chars=20,
                halign=Gtk.Align.START,
            )

        # Header for the widget
        header_text = self.get_header_text(item)
        header_label = make_label(header_text, 'grid-header-label')
        widget_box.pack_start(header_label, False, False, 0)

        # Extra info for the widget
        info_text = self.get_info_text(item)
        if info_text:
            info_label = make_label(info_text, 'grid-info-label')
            widget_box.pack_start(info_label, False, False, 0)

        # Download the cover art.
        def on_artwork_downloaded(f):
            artwork.set_from_file(f.result())
            artwork.set_loading(False)

        def start_loading():
            artwork.set_loading(True)

        cover_art_filename_future = self.get_cover_art_filename_future(
            item, before_download=start_loading)
        cover_art_filename_future.add_done_callback(on_artwork_downloaded)

        widget_box.show_all()
        return widget_box

    # Virtual Methods
    # =========================================================================
    def get_header_text(self, item) -> str:
        raise NotImplementedError(
            'get_header_text must be implemented by the inheritor of '
            'CoverArtGrid.')

    def get_info_text(self, item) -> Optional[str]:
        raise NotImplementedError(
            'get_info_text must be implemented by the inheritor of '
            'CoverArtGrid.')

    def get_model_list_future(self, before_download):
        raise NotImplementedError(
            'get_model_list_future must be implemented by the inheritor of '
            'CoverArtGrid.')

    def create_model_from_element(self, el):
        raise NotImplementedError(
            'create_model_from_element must be implemented by the inheritor '
            'of CoverArtGrid.')

    def get_cover_art_filename_future(self, item, before_download) -> Future:
        raise NotImplementedError(
            'get_cover_art_filename_future must be implemented by the '
            'inheritor of CoverArtGrid.')

    # Event Handlers
    # =========================================================================
    def on_child_activated(self, flowbox, child):
        self.emit('item-clicked', self.model[child.get_index()])
