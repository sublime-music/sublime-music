import datetime
from time import time
from typing import Any, Callable, cast, Iterable, List, Optional, Tuple

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from sublime.adapters import (
    AdapterManager,
    AlbumSearchQuery,
    api_objects as API,
    Result,
)
from sublime.config import AppConfiguration
from sublime.ui import util
from sublime.ui.common import AlbumWithSongs, IconButton, SpinnerImage


def _to_type(query_type: AlbumSearchQuery.Type) -> str:
    return {
        AlbumSearchQuery.Type.RANDOM: "random",
        AlbumSearchQuery.Type.NEWEST: "newest",
        AlbumSearchQuery.Type.FREQUENT: "frequent",
        AlbumSearchQuery.Type.RECENT: "recent",
        AlbumSearchQuery.Type.STARRED: "starred",
        AlbumSearchQuery.Type.ALPHABETICAL_BY_NAME: "alphabetical",
        AlbumSearchQuery.Type.ALPHABETICAL_BY_ARTIST: "alphabetical",
        AlbumSearchQuery.Type.YEAR_RANGE: "year_range",
        AlbumSearchQuery.Type.GENRE: "genre",
    }[query_type]


def _from_str(type_str: str) -> AlbumSearchQuery.Type:
    return {
        "random": AlbumSearchQuery.Type.RANDOM,
        "newest": AlbumSearchQuery.Type.NEWEST,
        "frequent": AlbumSearchQuery.Type.FREQUENT,
        "recent": AlbumSearchQuery.Type.RECENT,
        "starred": AlbumSearchQuery.Type.STARRED,
        "alphabetical_by_name": AlbumSearchQuery.Type.ALPHABETICAL_BY_NAME,
        "alphabetical_by_artist": AlbumSearchQuery.Type.ALPHABETICAL_BY_ARTIST,
        "year_range": AlbumSearchQuery.Type.YEAR_RANGE,
        "genre": AlbumSearchQuery.Type.GENRE,
    }[type_str]


class AlbumsPanel(Gtk.Box):
    __gsignals__ = {
        "song-clicked": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        "refresh-window": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    populating_genre_combo = False
    grid_order_token: int = 0

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        actionbar = Gtk.ActionBar()

        # Sort by
        actionbar.add(Gtk.Label(label="Sort"))
        self.sort_type_combo, self.sort_type_combo_store = self.make_combobox(
            (
                ("random", "randomly", True),
                ("genre", "by genre", AdapterManager.can_get_genres()),
                ("newest", "by most recently added", True),
                # ("highest", "by highest rated", True),  # TODO I don't t hink this
                # works anyway
                ("frequent", "by most played", True),
                ("recent", "by most recently played", True),
                ("alphabetical", "alphabetically", True),
                ("starred", "by starred only", True),
                ("year_range", "by year", True),
            ),
            self.on_type_combo_changed,
        )
        actionbar.pack_start(self.sort_type_combo)

        self.alphabetical_type_combo, _ = self.make_combobox(
            (("by_name", "by album name", True), ("by_artist", "by artist name", True)),
            self.on_alphabetical_type_change,
        )
        actionbar.pack_start(self.alphabetical_type_combo)

        # TODO: Sort genre combo box alphabetically?
        self.genre_combo, self.genre_combo_store = self.make_combobox(
            (), self.on_genre_change
        )
        actionbar.pack_start(self.genre_combo)

        next_decade = datetime.datetime.now().year + 10

        self.from_year_label = Gtk.Label(label="from")
        actionbar.pack_start(self.from_year_label)
        self.from_year_spin_button = Gtk.SpinButton.new_with_range(0, next_decade, 1)
        self.from_year_spin_button.connect("value-changed", self.on_year_changed)
        actionbar.pack_start(self.from_year_spin_button)

        self.to_year_label = Gtk.Label(label="to")
        actionbar.pack_start(self.to_year_label)
        self.to_year_spin_button = Gtk.SpinButton.new_with_range(0, next_decade, 1)
        self.to_year_spin_button.connect("value-changed", self.on_year_changed)
        actionbar.pack_start(self.to_year_spin_button)

        refresh = IconButton("view-refresh-symbolic", "Refresh list of albums")
        refresh.connect("clicked", self.on_refresh_clicked)
        actionbar.pack_end(refresh)

        self.add(actionbar)

        scrolled_window = Gtk.ScrolledWindow()
        self.grid = AlbumsGrid()
        self.grid.connect(
            "song-clicked", lambda _, *args: self.emit("song-clicked", *args),
        )
        self.grid.connect("cover-clicked", self.on_grid_cover_clicked)
        scrolled_window.add(self.grid)
        self.add(scrolled_window)

    def make_combobox(
        self,
        items: Iterable[Tuple[str, str, bool]],
        on_change: Callable[["AlbumsPanel", Gtk.ComboBox], None],
    ) -> Tuple[Gtk.ComboBox, Gtk.ListStore]:
        store = Gtk.ListStore(str, str, bool)
        for item in items:
            store.append(item)

        combo = Gtk.ComboBox.new_with_model(store)
        combo.set_id_column(0)
        combo.connect("changed", on_change)

        renderer_text = Gtk.CellRendererText()
        combo.pack_start(renderer_text, True)
        combo.add_attribute(renderer_text, "text", 1)
        combo.add_attribute(renderer_text, "sensitive", 2)

        return combo, store

    def populate_genre_combo(
        self, app_config: AppConfiguration = None, force: bool = False,
    ):
        if not AdapterManager.can_get_genres():
            return

        def get_genres_done(f: Result):
            try:
                new_store = [
                    (genre.name, genre.name, True) for genre in (f.result() or [])
                ]

                util.diff_song_store(self.genre_combo_store, new_store)

                if app_config:
                    current_genre_id = self.get_id(self.genre_combo)
                    genre = app_config.state.current_album_search_query.genre
                    if genre and current_genre_id != (genre_name := genre.name):
                        self.genre_combo.set_active_id(genre_name)
            finally:
                self.updating_query = False

        # Never force. We invalidate the cache ourselves (force is used when
        # sort params change). TODO I don't think taat is the case now probaly can just
        # force=force here
        genres_future = AdapterManager.get_genres(force=False)
        genres_future.add_done_callback(lambda f: GLib.idle_add(get_genres_done, f))

    def update(self, app_config: AppConfiguration = None, force: bool = False):
        self.updating_query = True

        # (En|Dis)able getting genres.
        self.sort_type_combo_store[1][2] = AdapterManager.can_get_genres()

        if app_config:
            self.current_query = app_config.state.current_album_search_query

        self.alphabetical_type_combo.set_active_id(
            {
                AlbumSearchQuery.Type.ALPHABETICAL_BY_NAME: "by_name",
                AlbumSearchQuery.Type.ALPHABETICAL_BY_ARTIST: "by_artist",
            }.get(self.current_query.type)
            or "by_name"
        )
        self.sort_type_combo.set_active_id(_to_type(self.current_query.type))

        if year_range := self.current_query.year_range:
            self.from_year_spin_button.set_value(year_range[0])
            self.to_year_spin_button.set_value(year_range[1])

        self.populate_genre_combo(app_config, force=force)

        # Show/hide the combo boxes.
        def show_if(sort_type: Iterable[AlbumSearchQuery.Type], *elements):
            for element in elements:
                if self.current_query.type in sort_type:
                    element.show()
                else:
                    element.hide()

        show_if(
            (
                AlbumSearchQuery.Type.ALPHABETICAL_BY_NAME,
                AlbumSearchQuery.Type.ALPHABETICAL_BY_ARTIST,
            ),
            self.alphabetical_type_combo,
        )
        show_if((AlbumSearchQuery.Type.GENRE,), self.genre_combo)
        show_if(
            (AlbumSearchQuery.Type.YEAR_RANGE,),
            self.from_year_label,
            self.from_year_spin_button,
            self.to_year_label,
            self.to_year_spin_button,
        )

        # At this point, the current query should be totally updated.
        self.grid_order_token = self.grid.update_params(self.current_query)
        self.grid.update(self.grid_order_token, app_config, force=force)

    def get_id(self, combo: Gtk.ComboBox) -> Optional[str]:
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            return combo.get_model()[tree_iter][0]
        return None

    def on_refresh_clicked(self, button: Any):
        self.emit("refresh-window", {}, True)

    class _Genre(API.Genre):
        def __init__(self, name: str):
            self.name = name

    def on_type_combo_changed(self, combo: Gtk.ComboBox):
        id = self.get_id(combo)
        assert id
        if id == "alphabetical":
            id += "_" + cast(str, self.get_id(self.alphabetical_type_combo))
        self.emit_if_not_updating(
            "refresh-window",
            {
                "current_album_search_query": AlbumSearchQuery(
                    _from_str(id),
                    self.current_query.year_range,
                    self.current_query.genre,
                )
            },
            False,
        )

    def on_alphabetical_type_change(self, combo: Gtk.ComboBox):
        id = "alphabetical_" + cast(str, self.get_id(combo))
        self.emit_if_not_updating(
            "refresh-window",
            {
                "current_album_search_query": AlbumSearchQuery(
                    _from_str(id),
                    self.current_query.year_range,
                    self.current_query.genre,
                )
            },
            False,
        )

    def on_genre_change(self, combo: Gtk.ComboBox):
        genre = self.get_id(combo)
        assert genre
        self.emit_if_not_updating(
            "refresh-window",
            {
                "current_album_search_query": AlbumSearchQuery(
                    self.current_query.type,
                    self.current_query.year_range,
                    AlbumsPanel._Genre(genre),
                )
            },
            False,
        )

    def on_year_changed(self, entry: Gtk.SpinButton) -> bool:
        year = int(entry.get_value())
        assert self.current_query.year_range
        if self.to_year_spin_button == entry:
            new_year_tuple = (self.current_query.year_range[0], year)
        else:
            new_year_tuple = (year, self.current_query.year_range[0])

        self.emit_if_not_updating(
            "refresh-window",
            {
                "current_album_search_query": AlbumSearchQuery(
                    self.current_query.type, new_year_tuple, self.current_query.genre
                )
            },
            False,
        )

        return False

    def on_grid_cover_clicked(self, grid: Any, id: str):
        self.emit(
            "refresh-window", {"selected_album_id": id}, False,
        )

    def emit_if_not_updating(self, *args):
        if self.updating_query:
            return
        self.emit(*args)


class AlbumsGrid(Gtk.Overlay):
    """Defines the albums panel."""

    __gsignals__ = {
        "song-clicked": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        "cover-clicked": (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (object,),),
    }

    current_query: AlbumSearchQuery = AlbumSearchQuery(AlbumSearchQuery.Type.RANDOM)
    latest_applied_order_ratchet: int = 0
    order_ratchet: int = 0

    currently_selected_index: Optional[int] = None
    currently_selected_id: Optional[str] = None
    next_page_fn = None
    current_min_size_request = 30
    # server_hash = None

    class _AlbumModel(GObject.Object):
        def __init__(self, album: API.Album):
            self.album = album
            super().__init__()

        @property
        def id(self) -> str:
            return self.album.id

        def __repr__(self) -> str:
            return f"<AlbumsGrid.AlbumModel {self.album}>"

    def update_params(self, query: AlbumSearchQuery) -> int:
        # If there's a diff, increase the ratchet.
        if hash(self.current_query) != hash(query):
            self.order_ratchet += 1
        self.current_query = query
        self.current_min_size_request = 30
        return self.order_ratchet

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.items_per_row = 4

        scrolled_window = Gtk.ScrolledWindow()
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
        self.grid_top.connect("child-activated", self.on_child_activated)
        self.grid_top.connect("size-allocate", self.on_grid_resize)

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
        self.grid_bottom.connect("child-activated", self.on_child_activated)

        self.list_store_bottom = Gio.ListStore()
        self.grid_bottom.bind_model(self.list_store_bottom, self.create_widget)

        grid_detail_grid_box.add(self.grid_bottom)

        scrolled_window.add(grid_detail_grid_box)
        self.add(scrolled_window)

        self.spinner = Gtk.Spinner(
            name="grid-spinner",
            active=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        self.add_overlay(self.spinner)

    def update(
        self, order_token: int, app_config: AppConfiguration, force: bool = False
    ):
        if order_token < self.latest_applied_order_ratchet:
            return

        if app_config:
            self.currently_selected_id = app_config.state.selected_album_id

        # TODO test this
        # new_hash = app_config.server.strhash()
        # server_changed = self.server_hash != new_hash
        # self.server_hash = new_hash
        self.update_grid(
            order_token, force=force,  # or server_changed,
        )

        # Update the detail panel.
        children = self.detail_box_inner.get_children()
        if len(children) > 0 and hasattr(children[0], "update"):
            children[0].update(force=force)

    error_dialog = None

    def update_grid(self, order_token: int, force: bool = False):
        if not AdapterManager.can_get_artists():
            self.spinner.hide()
            return

        def do_update(f: Result[Iterable[API.Album]]):
            try:
                albums = f.result()
            except Exception as e:
                if self.error_dialog:
                    self.spinner.hide()
                    return
                self.error_dialog = Gtk.MessageDialog(
                    transient_for=self.get_toplevel(),
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Failed to retrieve albums",
                )
                self.error_dialog.format_secondary_markup(
                    # TODO make this error better
                    f"Getting albums by {self.current_query.type} failed due to the "
                    f"following error\n\n{e}"
                )
                self.error_dialog.run()
                self.error_dialog.destroy()
                self.error_dialog = None
                self.spinner.hide()
                return

            # Don't override more recent results
            if order_token < self.latest_applied_order_ratchet:
                return

            should_reload = (
                force or self.latest_applied_order_ratchet < self.order_ratchet
            )
            self.latest_applied_order_ratchet = self.order_ratchet

            selected_index = None
            models = []
            for i, album in enumerate(albums):
                model = AlbumsGrid._AlbumModel(album)

                if model.id == self.currently_selected_id:
                    selected_index = i

                models.append(model)

            selection_changed = selected_index != self.currently_selected_index
            self.currently_selected_index = selected_index
            self.reflow_grids(
                force_reload_from_master=should_reload,
                selection_changed=selection_changed,
                models=models,
            )
            self.spinner.hide()

        future = AdapterManager.get_albums(
            self.current_query,
            before_download=lambda: GLib.idle_add(self.spinner.show),
            force=force,
        )
        future.add_done_callback(lambda f: GLib.idle_add(do_update, f))

    # Event Handlers
    # =========================================================================
    def on_child_activated(self, flowbox: Gtk.FlowBox, child: Gtk.Widget):
        click_top = flowbox == self.grid_top
        selected_index = child.get_index()

        if click_top:
            if selected_index == self.currently_selected_index:
                self.emit("cover-clicked", None)
            else:
                self.emit("cover-clicked", self.list_store_top[selected_index].id)
        else:
            self.emit("cover-clicked", self.list_store_bottom[selected_index].id)

    def on_grid_resize(self, flowbox: Gtk.FlowBox, rect: Gdk.Rectangle):
        # TODO (#124): this doesn't work with themes that add extra padding.
        # 200     + (10      * 2) + (5      * 2) = 230
        # picture + (padding * 2) + (margin * 2)
        new_items_per_row = min((rect.width // 230), 7)
        if new_items_per_row != self.items_per_row:
            self.items_per_row = min((rect.width // 230), 7)
            self.detail_box_inner.set_size_request(
                self.items_per_row * 230 - 10, -1,
            )

            self.reflow_grids()

    # Helper Methods
    # =========================================================================
    def create_widget(self, item: _AlbumModel) -> Gtk.Box:
        widget_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Cover art image
        artwork = SpinnerImage(
            loading=False,
            image_name="grid-artwork",
            spinner_name="grid-artwork-spinner",
            image_size=200,
        )
        widget_box.pack_start(artwork, False, False, 0)

        def make_label(text: str, name: str) -> Gtk.Label:
            return Gtk.Label(
                name=name,
                label=text,
                tooltip_text=text,
                ellipsize=Pango.EllipsizeMode.END,
                max_width_chars=20,
                halign=Gtk.Align.START,
            )

        # Header for the widget
        header_label = make_label(item.album.name, "grid-header-label")
        widget_box.pack_start(header_label, False, False, 0)

        # Extra info for the widget
        info_text = util.dot_join(
            item.album.artist.name if item.album.artist else "-", item.album.year
        )
        if info_text:
            info_label = make_label(info_text, "grid-info-label")
            widget_box.pack_start(info_label, False, False, 0)

        # Download the cover art.
        def on_artwork_downloaded(f: Result[str]):
            artwork.set_from_file(f.result())
            artwork.set_loading(False)

        def start_loading():
            artwork.set_loading(True)

        cover_art_filename_future = AdapterManager.get_cover_art_filename(
            item.album.cover_art, before_download=lambda: GLib.idle_add(start_loading),
        )
        cover_art_filename_future.add_done_callback(
            lambda f: GLib.idle_add(on_artwork_downloaded, f)
        )

        widget_box.show_all()
        return widget_box

    def reflow_grids(
        self,
        force_reload_from_master: bool = False,
        selection_changed: bool = False,
        models: List[_AlbumModel] = None,
    ):
        # Determine where the cuttoff is between the top and bottom grids.
        store = models if models is not None else self.list_store_top
        entries_before_fold = len(store)
        if self.currently_selected_index is not None and self.items_per_row:
            entries_before_fold = (
                (self.currently_selected_index // self.items_per_row) + 1
            ) * self.items_per_row

        if force_reload_from_master:
            # Just remove everything and re-add all of the items.
            # TODO (#114): make this smarter somehow to avoid flicker. Maybe
            # change this so that it removes one by one and adds back one by
            # one.
            self.list_store_top.splice(
                0, len(self.list_store_top), store[:entries_before_fold]
            )
            self.list_store_bottom.splice(
                0, len(self.list_store_bottom), store[entries_before_fold:]
            )
        else:
            top_store_len = len(self.list_store_top)
            bottom_store_len = len(self.list_store_bottom)
            diff = abs(entries_before_fold - top_store_len)

            if diff > 0:
                if entries_before_fold - top_store_len > 0:
                    # Move entries from the bottom store.
                    self.list_store_top.splice(
                        top_store_len, 0, self.list_store_bottom[:diff]
                    )
                    self.list_store_bottom.splice(0, min(diff, bottom_store_len), [])
                else:
                    # Move entries to the bottom store.
                    self.list_store_bottom.splice(0, 0, self.list_store_top[-diff:])
                    self.list_store_top.splice(top_store_len - diff, diff, [])

        if self.currently_selected_index is not None:
            to_select = self.grid_top.get_child_at_index(self.currently_selected_index)
            if not to_select:
                return
            self.grid_top.select_child(to_select)

            if not selection_changed:
                return

            for c in self.detail_box_inner.get_children():
                self.detail_box_inner.remove(c)

            model = self.list_store_top[self.currently_selected_index]
            detail_element = AlbumWithSongs(model.album, cover_art_size=300)
            detail_element.connect(
                "song-clicked", lambda _, *args: self.emit("song-clicked", *args),
            )
            detail_element.connect("song-selected", lambda *a: None)

            self.detail_box_inner.pack_start(detail_element, True, True, 0)
            self.detail_box.show_all()

            # TODO (#88): scroll so that the grid_top is visible, and the
            # detail_box is visible, with preference to the grid_top. May need
            # to add another flag for this function.
        else:
            self.grid_top.unselect_all()
            self.detail_box.hide()
