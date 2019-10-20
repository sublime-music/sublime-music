from concurrent.futures import Future
from typing import Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk, GObject, Gio, Pango

from sublime.state_manager import ApplicationState
from sublime.cache_manager import CacheManager
from .spinner_image import SpinnerImage


class CoverArtGrid(Gtk.ScrolledWindow):
    """Defines a grid with cover art."""
    __gsignals__ = {
        'song-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object, object),
        ),
        'cover-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, ),
        ),
    }

    current_selection = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.model_list_future_generator = None

        # This is the master list.
        self.list_store = Gio.ListStore()

        self.items_per_row = 4

        overlay = Gtk.Overlay()
        grid_detail_grid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.grid_top = Gtk.FlowBox(
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
        self.grid_top.connect('size-allocate', self.on_grid_resize)

        self.list_store_top = Gio.ListStore()
        self.grid_top.bind_model(self.list_store_top, self.create_widget)

        grid_detail_grid_box.add(self.grid_top)

        self.detail_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.detail_box.pack_start(Gtk.Box(), True, True, 0)

        self.detail_box_inner = Gtk.Box()
        self.detail_box.pack_start(self.detail_box_inner, False, False, 0)

        self.detail_box.pack_start(Gtk.Box(), True, True, 0)
        grid_detail_grid_box.add(self.detail_box)

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

    def update(
            self,
            state: ApplicationState = None,
            force: bool = False,
            selected_id: str = None,
    ):
        self.update_grid(force=force, selected_id=selected_id)

        # Update the detail panel.
        children = self.detail_box_inner.get_children()
        if len(children) > 0 and hasattr(children[0], 'update'):
            children[0].update(force=force)

    def update_grid(self, force=False, selected_id=None):
        def reflow_grid(force_reload, selected_index):
            selection_changed = (selected_index != self.current_selection)
            self.current_selection = selected_index
            self.reflow_grids(
                force_reload_from_master=force_reload,
                selection_changed=selection_changed,
            )
            self.spinner.hide()

        # If we don't have a generator yet, then we need to get one.
        self.model_list_future_generator = (
            self.get_new_model_generator(
                before_download=lambda: GLib.idle_add(self.spinner.show),
                force=force,
            ))

        old_len = len(self.list_store)
        self.list_store.remove_all()

        i = 0
        selected_index = None
        while True:
            try:
                next_el = next(self.model_list_future_generator)
            except StopIteration:
                break

            # Stop once we hit a network barrier (unless the list hasn't
            # been loaded).
            if next_el == 'network barrier':
                if len(self.list_store) == 0:
                    continue
                else:
                    break

            model = self.create_model_from_element(next_el)
            if model.id == selected_id:
                selected_index = i
            i += 1

            self.list_store.append(model)

        GLib.idle_add(
            reflow_grid,
            old_len != len(self.list_store) or force,
            selected_index,
        )

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

    def reflow_grids(
            self,
            force_reload_from_master=False,
            selection_changed=False,
    ):
        # Determine where the cuttoff is between the top and bottom grids.
        entries_before_fold = len(self.list_store)
        if self.current_selection is not None and self.items_per_row:
            entries_before_fold = (
                ((self.current_selection // self.items_per_row) + 1)
                * self.items_per_row)

        if force_reload_from_master:
            # Just remove everything and re-add all of the items.
            self.list_store_top.remove_all()
            self.list_store_bottom.remove_all()

            for e in self.list_store[:entries_before_fold]:
                self.list_store_top.append(e)

            for e in self.list_store[entries_before_fold:]:
                self.list_store_bottom.append(e)
        else:
            top_diff = len(self.list_store_top) - entries_before_fold

            if top_diff < 0:
                # Move entries from the bottom store.
                for e in self.list_store_bottom[:-top_diff]:
                    self.list_store_top.append(e)
                for _ in range(-top_diff):
                    if len(self.list_store_bottom) == 0:
                        break
                    del self.list_store_bottom[0]
            else:
                # Move entries to the bottom store.
                for e in reversed(self.list_store_top[entries_before_fold:]):
                    self.list_store_bottom.insert(0, e)
                for _ in range(top_diff):
                    del self.list_store_top[-1]

        if self.current_selection is not None:
            if not selection_changed:
                return

            # TODO: only do this if the selection actually changed.
            self.grid_top.select_child(
                self.grid_top.get_child_at_index(self.current_selection))

            for c in self.detail_box_inner.get_children():
                self.detail_box_inner.remove(c)

            model = self.list_store[self.current_selection]
            detail_element = self.create_detail_element_from_model(model)
            detail_element.connect(
                'song-clicked',
                lambda _, song, queue, metadata: self.emit(
                    'song-clicked', song, queue, metadata),
            )
            detail_element.connect('song-selected', lambda *a: None)

            self.detail_box_inner.pack_start(detail_element, True, True, 0)
            self.detail_box.show_all()

            # TODO scroll so that the grid_top is visible, and the detail_box
            # is visible, with preference to the grid_top.
        else:
            self.grid_top.unselect_all()
            self.detail_box.hide()

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

    def get_new_model_generator(self, before_download, force=False):
        raise NotImplementedError(
            'get_new_model_generator must be implemented by the inheritor of '
            'CoverArtGrid.')

    def create_model_from_element(self, el):
        raise NotImplementedError(
            'create_model_from_element must be implemented by the inheritor '
            'of CoverArtGrid.')

    def create_detail_element_from_model(self, model):
        raise NotImplementedError(
            'create_detail_element_from_model must be implemented by the '
            'inheritor of CoverArtGrid.')

    def get_cover_art_filename_future(self, item, before_download) -> Future:
        raise NotImplementedError(
            'get_cover_art_filename_future must be implemented by the '
            'inheritor of CoverArtGrid.')

    # Event Handlers
    # =========================================================================
    def on_child_activated(self, flowbox, child):
        click_top = flowbox == self.grid_top
        selected_index = (
            child.get_index() + (0 if click_top else len(self.list_store_top)))

        if selected_index == self.current_selection:
            self.emit('cover-clicked', None)
        else:
            self.emit('cover-clicked', self.list_store[selected_index].id)

    def on_grid_resize(self, flowbox, rect):
        # TODO: this doesn't work with themes that add extra padding.
        # 200     + (10      * 2) + (5      * 2) = 230
        # picture + (padding * 2) + (margin * 2)
        new_items_per_row = min((rect.width // 230), 7)
        if new_items_per_row != self.items_per_row:
            self.items_per_row = min((rect.width // 230), 7)
            self.detail_box_inner.set_size_request(
                self.items_per_row * 230 - 10,
                -1,
            )

            self.reflow_grids()
