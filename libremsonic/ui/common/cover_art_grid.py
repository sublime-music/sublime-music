from concurrent.futures import Future
import math
from typing import Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk, GObject, Gio, Pango

from libremsonic.ui import util
from libremsonic.state_manager import ApplicationState
from .spinner_image import SpinnerImage


class CoverArtGrid(Gtk.ScrolledWindow):
    """Defines a grid with cover art."""
    __gsignals__ = {
        'song-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, ),
        )
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # This is the root model. It stores the master list.
        self.list_store = Gio.ListStore()
        self.selected_list_store_index = None

        overlay = Gtk.Overlay()
        grid_detail_grid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.grid_top = Gtk.FlowBox(
            vexpand=True,
            hexpand=True,
            row_spacing=5,
            column_spacing=5,
            margin_top=12,
            margin_bottom=12,
            homogeneous=True,
            valign=Gtk.Align.START,
            halign=Gtk.Align.CENTER,
            selection_mode=Gtk.SelectionMode.SINGLE,
        )
        self.grid_top.connect('child-activated', self.on_child_activated)

        self.list_store_top = Gio.ListStore()
        self.grid_top.bind_model(self.list_store_top, self.create_widget)

        grid_detail_grid_box.add(self.grid_top)

        grid_detail_grid_box.add(Gtk.Label('foo'))

        self.grid_bottom = Gtk.FlowBox(
            vexpand=True,
            hexpand=True,
            row_spacing=5,
            column_spacing=5,
            margin_top=12,
            margin_bottom=12,
            homogeneous=True,
            valign=Gtk.Align.START,
            halign=Gtk.Align.CENTER,
            selection_mode=Gtk.SelectionMode.SINGLE,
        )
        self.grid_bottom.connect('child-activated', self.on_child_activated)

        self.list_store_bottom = Gio.ListStore()
        self.grid_bottom.bind_model(self.list_store_bottom, self.create_widget)

        grid_detail_grid_box.add(self.grid_bottom)

        overlay.add(grid_detail_grid_box)

        self.spinner = Gtk.Spinner(
            name='grid-spinner',
            active=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        overlay.add_overlay(self.spinner)

        self.add(overlay)

    def update(self, state: ApplicationState = None):
        self.update_grid()

    def update_grid(self):
        def start_loading():
            self.spinner.show()

        def stop_loading():
            self.spinner.hide()

        def future_done(f):
            try:
                result = f.result()
            except Exception as e:
                print('fail', e)
                return

            currently_selected = self.grid_top.get_selected_children()

            self.list_store.remove_all()
            for el in result:
                self.list_store.append(self.create_model_from_element(el))

            self.reflow_grids()
            stop_loading()

        future = self.get_model_list_future(before_download=start_loading)
        future.add_done_callback(lambda f: GLib.idle_add(future_done, f))

    def create_widget(self, item):
        widget_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Cover art image
        artwork = SpinnerImage(
            loading=False,
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
            item, before_download=lambda: GLib.idle_add(start_loading))
        cover_art_filename_future.add_done_callback(
            lambda f: GLib.idle_add(on_artwork_downloaded, f))

        widget_box.show_all()
        return widget_box

    def reflow_grids(self):
        # TODO calculate this somehow
        covers_per_row = 4

        # Determine where the cuttoff is between the top and bottom grids.
        entries_before_fold = len(self.list_store)
        if self.selected_list_store_index is not None:
            entries_before_fold = ((
                (self.selected_list_store_index // covers_per_row) + 1)
                                   * covers_per_row)
            print(entries_before_fold)

        # TODO should do diffing on the actual updates here:
        # Split the list_store into top and bottom.
        util.diff_model(self.list_store_top,
                        self.list_store[:entries_before_fold])
        util.diff_model(self.list_store_bottom,
                        self.list_store[entries_before_fold:])

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
        click_top = flowbox == self.grid_top
        self.selected_list_store_index = (
            child.get_index() + (0 if click_top else len(self.list_store_top)))

        print('item clicked', self.list_store[self.selected_list_store_index])
        self.reflow_grids()
