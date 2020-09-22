import datetime
import itertools
import logging
import math
from typing import Any, Callable, cast, Iterable, List, Optional, Tuple

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from ..adapters import (
    AdapterManager,
    AlbumSearchQuery,
    api_objects as API,
    CacheMissError,
    Result,
)
from ..config import AppConfiguration
from ..ui import util
from ..ui.common import AlbumWithSongs, IconButton, LoadError, SpinnerImage


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

    offline_mode = False
    populating_genre_combo = False
    grid_order_token: int = 0
    album_sort_direction: str = "ascending"
    album_page_size: int = 30
    album_page: int = 0
    grid_pages_count: int = 0

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

        self.genre_combo, self.genre_combo_store = self.make_combobox(
            (), self.on_genre_change
        )
        actionbar.pack_start(self.genre_combo)

        next_decade = (datetime.datetime.now().year // 10) * 10 + 10

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

        self.sort_toggle = IconButton(
            "view-sort-descending-symbolic", "Sort descending", relief=True
        )
        self.sort_toggle.connect("clicked", self.on_sort_toggle_clicked)
        actionbar.pack_start(self.sort_toggle)

        # Add the page widget.
        page_widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.prev_page = IconButton(
            "go-previous-symbolic", "Go to the previous page", sensitive=False
        )
        self.prev_page.connect("clicked", self.on_prev_page_clicked)
        page_widget.add(self.prev_page)
        page_widget.add(Gtk.Label(label="Page"))
        self.page_entry = Gtk.Entry()
        self.page_entry.set_width_chars(1)
        self.page_entry.set_max_width_chars(1)
        self.page_entry.connect("changed", self.on_page_entry_changed)
        self.page_entry.connect("insert-text", self.on_page_entry_insert_text)
        page_widget.add(self.page_entry)
        page_widget.add(Gtk.Label(label="of"))
        self.page_count_label = Gtk.Label(label="-")
        page_widget.add(self.page_count_label)
        self.next_page = IconButton(
            "go-next-symbolic", "Go to the next page", sensitive=False
        )
        self.next_page.connect("clicked", self.on_next_page_clicked)
        page_widget.add(self.next_page)
        actionbar.set_center_widget(page_widget)

        self.refresh_button = IconButton(
            "view-refresh-symbolic", "Refresh list of albums", relief=True
        )
        self.refresh_button.connect("clicked", self.on_refresh_clicked)
        actionbar.pack_end(self.refresh_button)

        actionbar.pack_end(Gtk.Label(label="albums per page"))
        self.show_count_dropdown, _ = self.make_combobox(
            ((x, x, True) for x in ("20", "30", "40", "50")),
            self.on_show_count_dropdown_change,
        )
        actionbar.pack_end(self.show_count_dropdown)
        actionbar.pack_end(Gtk.Label(label="Show"))

        self.add(actionbar)

        scrolled_window = Gtk.ScrolledWindow()
        self.grid = AlbumsGrid()
        self.grid.connect(
            "song-clicked",
            lambda _, *args: self.emit("song-clicked", *args),
        )
        self.grid.connect(
            "refresh-window",
            lambda _, *args: self.emit("refresh-window", *args),
        )
        self.grid.connect("cover-clicked", self.on_grid_cover_clicked)
        self.grid.connect("num-pages-changed", self.on_grid_num_pages_changed)
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
        self,
        app_config: AppConfiguration = None,
        force: bool = False,
    ):
        if not AdapterManager.can_get_genres():
            self.updating_query = False
            return

        def get_genres_done(f: Result):
            try:
                genre_names = map(lambda g: g.name, f.result() or [])
                new_store = [(name, name, True) for name in sorted(genre_names)]

                util.diff_song_store(self.genre_combo_store, new_store)

                if app_config:
                    current_genre_id = self.get_id(self.genre_combo)
                    genre = app_config.state.current_album_search_query.genre
                    if genre and current_genre_id != (genre_name := genre.name):
                        self.genre_combo.set_active_id(genre_name)
            finally:
                self.updating_query = False

        try:
            force = force and (
                app_config is not None
                and (state := app_config.state) is not None
                and state.current_album_search_query.type == AlbumSearchQuery.Type.GENRE
            )
            genres_future = AdapterManager.get_genres(force=force)
            genres_future.add_done_callback(lambda f: GLib.idle_add(get_genres_done, f))
        except Exception:
            self.updating_query = False

    def update(self, app_config: AppConfiguration = None, force: bool = False):
        self.updating_query = True

        supported_type_strings = {
            _to_type(t) for t in AdapterManager.get_supported_artist_query_types()
        }
        for i, el in enumerate(self.sort_type_combo_store):
            self.sort_type_combo_store[i][2] = el[0] in supported_type_strings

        # (En|Dis)able getting genres.
        self.sort_type_combo_store[1][2] = AdapterManager.can_get_genres()

        if app_config:
            self.current_query = app_config.state.current_album_search_query
            self.offline_mode = app_config.offline_mode

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

        # Update the page display
        if app_config:
            self.album_page = app_config.state.album_page
            self.album_page_size = app_config.state.album_page_size
            self.refresh_button.set_sensitive(not app_config.offline_mode)

        self.prev_page.set_sensitive(self.album_page > 0)
        self.page_entry.set_text(str(self.album_page + 1))

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

        # (En|Dis)able the sort button
        self.sort_toggle.set_sensitive(
            self.current_query.type != AlbumSearchQuery.Type.RANDOM
        )

        if app_config:
            self.album_sort_direction = app_config.state.album_sort_direction
            self.sort_toggle.set_icon(f"view-sort-{self.album_sort_direction}-symbolic")
            self.sort_toggle.set_tooltip_text(
                "Change sort order to "
                + self._get_opposite_sort_dir(self.album_sort_direction)
            )

            self.show_count_dropdown.set_active_id(
                str(app_config.state.album_page_size)
            )

        # Has to be last because it resets self.updating_query
        self.populate_genre_combo(app_config, force=force)

        # At this point, the current query should be totally updated.
        self.grid_order_token = self.grid.update_params(app_config)
        self.grid.update(self.grid_order_token, app_config, force=force)

    def _get_opposite_sort_dir(self, sort_dir: str) -> str:
        return ("ascending", "descending")[0 if sort_dir == "descending" else 1]

    def get_id(self, combo: Gtk.ComboBox) -> Optional[str]:
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            return combo.get_model()[tree_iter][0]
        return None

    def on_sort_toggle_clicked(self, _):
        self.emit(
            "refresh-window",
            {
                "album_sort_direction": self._get_opposite_sort_dir(
                    self.album_sort_direction
                ),
                "album_page": 0,
                "selected_album_id": None,
            },
            False,
        )

    def on_refresh_clicked(self, _):
        self.emit("refresh-window", {}, True)

    class _Genre(API.Genre):
        def __init__(self, name: str):
            self.name = name

    def on_grid_num_pages_changed(self, grid: Any, pages: int):
        self.grid_pages_count = pages
        pages_str = str(self.grid_pages_count)
        self.page_count_label.set_text(pages_str)
        self.next_page.set_sensitive(self.album_page < self.grid_pages_count - 1)
        num_digits = len(pages_str)
        self.page_entry.set_width_chars(num_digits)
        self.page_entry.set_max_width_chars(num_digits)

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
                ),
                "album_page": 0,
                "selected_album_id": None,
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
                ),
                "album_page": 0,
                "selected_album_id": None,
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
                ),
                "album_page": 0,
                "selected_album_id": None,
            },
            False,
        )

    def on_year_changed(self, entry: Gtk.SpinButton) -> bool:
        year = int(entry.get_value())
        assert self.current_query.year_range
        if self.to_year_spin_button == entry:
            new_year_tuple = (self.current_query.year_range[0], year)
        else:
            new_year_tuple = (year, self.current_query.year_range[1])

        self.emit_if_not_updating(
            "refresh-window",
            {
                "current_album_search_query": AlbumSearchQuery(
                    self.current_query.type, new_year_tuple, self.current_query.genre
                ),
                "album_page": 0,
                "selected_album_id": None,
            },
            False,
        )

        return False

    def on_page_entry_changed(self, entry: Gtk.Entry) -> bool:
        if len(text := entry.get_text()) > 0:
            self.emit_if_not_updating(
                "refresh-window",
                {"album_page": int(text) - 1, "selected_album_id": None},
                False,
            )
        return False

    def on_page_entry_insert_text(
        self, entry: Gtk.Entry, text: str, length: int, position: int
    ) -> bool:
        if self.updating_query:
            return False
        if not text.isdigit():
            entry.emit_stop_by_name("insert-text")
            return True
        page_num = int(entry.get_text() + text)
        if self.grid_pages_count is None or self.grid_pages_count < page_num:
            entry.emit_stop_by_name("insert-text")
            return True
        return False

    def on_prev_page_clicked(self, _):
        self.emit_if_not_updating(
            "refresh-window",
            {"album_page": self.album_page - 1, "selected_album_id": None},
            False,
        )

    def on_next_page_clicked(self, _):
        self.emit_if_not_updating(
            "refresh-window",
            {"album_page": self.album_page + 1, "selected_album_id": None},
            False,
        )

    def on_grid_cover_clicked(self, grid: Any, id: str):
        self.emit(
            "refresh-window",
            {"selected_album_id": id},
            False,
        )

    def on_show_count_dropdown_change(self, combo: Gtk.ComboBox):
        show_count = int(self.get_id(combo) or 30)
        self.emit(
            "refresh-window",
            {"album_page_size": show_count, "album_page": 0},
            False,
        )

    def emit_if_not_updating(self, *args):
        if self.updating_query:
            return
        self.emit(*args)


class AlbumsGrid(Gtk.Overlay):
    """Defines the albums panel."""

    __gsignals__ = {
        "cover-clicked": (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (object,)),
        "refresh-window": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
        "song-clicked": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        "num-pages-changed": (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (int,)),
    }

    class _AlbumModel(GObject.Object):
        def __init__(self, album: API.Album):
            self.album = album
            super().__init__()

        @property
        def id(self) -> str:
            assert self.album.id
            return self.album.id

        def __repr__(self) -> str:
            return f"<AlbumsGrid._AlbumModel {self.album}>"

    current_query: AlbumSearchQuery = AlbumSearchQuery(AlbumSearchQuery.Type.RANDOM)
    current_models: List[_AlbumModel] = []
    latest_applied_order_ratchet: int = 0
    order_ratchet: int = 0
    offline_mode: bool = False

    currently_selected_index: Optional[int] = None
    currently_selected_id: Optional[str] = None
    sort_dir: str = ""
    page_size: int = 30
    page: int = 0
    num_pages: Optional[int] = None
    next_page_fn = None
    provider_id: Optional[str] = None

    def update_params(self, app_config: AppConfiguration) -> int:
        # If there's a diff, increase the ratchet.
        if (
            self.current_query.strhash()
            != (search_query := app_config.state.current_album_search_query).strhash()
        ):
            self.order_ratchet += 1
            self.current_query = search_query

        if self.offline_mode != (offline_mode := app_config.offline_mode):
            self.order_ratchet += 1
            self.offline_mode = offline_mode

        if self.provider_id != (provider_id := app_config.current_provider_id):
            self.order_ratchet += 1
            self.provider_id = provider_id

        return self.order_ratchet

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.items_per_row = 4

        scrolled_window = Gtk.ScrolledWindow()
        grid_detail_grid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.error_container = Gtk.Box()
        grid_detail_grid_box.add(self.error_container)

        def create_flowbox(**kwargs) -> Gtk.FlowBox:
            flowbox = Gtk.FlowBox(
                **kwargs,
                hexpand=True,
                row_spacing=5,
                column_spacing=5,
                margin_top=5,
                homogeneous=True,
                valign=Gtk.Align.START,
                halign=Gtk.Align.CENTER,
                selection_mode=Gtk.SelectionMode.SINGLE,
            )
            flowbox.set_max_children_per_line(7)
            return flowbox

        self.grid_top = create_flowbox()
        self.grid_top.connect("child-activated", self.on_child_activated)
        self.grid_top.connect("size-allocate", self.on_grid_resize)

        self.list_store_top = Gio.ListStore()
        self.grid_top.bind_model(self.list_store_top, self._create_cover_art_widget)

        grid_detail_grid_box.add(self.grid_top)

        self.detail_box_revealer = Gtk.Revealer(valign=Gtk.Align.END)
        self.detail_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, name="artist-detail-box"
        )
        self.detail_box.pack_start(Gtk.Box(), True, True, 0)

        self.detail_box_inner = Gtk.Box()
        self.detail_box.pack_start(self.detail_box_inner, False, False, 0)

        self.detail_box.pack_start(Gtk.Box(), True, True, 0)
        self.detail_box_revealer.add(self.detail_box)
        grid_detail_grid_box.add(self.detail_box_revealer)

        self.grid_bottom = create_flowbox(vexpand=True)
        self.grid_bottom.connect("child-activated", self.on_child_activated)

        self.list_store_bottom = Gio.ListStore()
        self.grid_bottom.bind_model(
            self.list_store_bottom, self._create_cover_art_widget
        )

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
        self, order_token: int, app_config: AppConfiguration = None, force: bool = False
    ):
        if order_token < self.latest_applied_order_ratchet:
            return

        force_grid_reload_from_master = False
        if app_config:
            self.currently_selected_id = app_config.state.selected_album_id

            if (
                self.sort_dir != app_config.state.album_sort_direction
                or self.page_size != app_config.state.album_page_size
                or self.page != app_config.state.album_page
            ):
                force_grid_reload_from_master = True
            self.sort_dir = app_config.state.album_sort_direction
            self.page_size = app_config.state.album_page_size
            self.page = app_config.state.album_page

        self.update_grid(
            order_token,
            use_ground_truth_adapter=force,
            force_grid_reload_from_master=force_grid_reload_from_master,
        )

        # Update the detail panel.
        children = self.detail_box_inner.get_children()
        if len(children) > 0 and hasattr(children[0], "update"):
            children[0].update(app_config=app_config, force=force)

    error_dialog = None

    def update_grid(
        self,
        order_token: int,
        use_ground_truth_adapter: bool = False,
        force_grid_reload_from_master: bool = False,
    ):
        if not AdapterManager.can_get_artists():
            self.spinner.hide()
            return

        force_grid_reload_from_master = (
            force_grid_reload_from_master
            or use_ground_truth_adapter
            or self.latest_applied_order_ratchet < order_token
        )

        def do_update_grid(selected_index: Optional[int]):
            if self.sort_dir == "descending" and selected_index:
                selected_index = len(self.current_models) - selected_index - 1

            self.reflow_grids(
                force_reload_from_master=force_grid_reload_from_master,
                selected_index=selected_index,
                models=self.current_models,
            )
            self.spinner.hide()

        def reload_store(f: Result[Iterable[API.Album]]):
            # Don't override more recent results
            if order_token < self.latest_applied_order_ratchet:
                return
            self.latest_applied_order_ratchet = order_token

            is_partial = False
            try:
                albums = list(f.result())
            except CacheMissError as e:
                albums = cast(Optional[List[API.Album]], e.partial_data) or []
                is_partial = True
            except Exception as e:
                if self.error_dialog:
                    self.spinner.hide()
                    return
                # TODO (#122): make this non-modal
                self.error_dialog = Gtk.MessageDialog(
                    transient_for=self.get_toplevel(),
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Failed to retrieve albums",
                )
                self.error_dialog.format_secondary_markup(
                    # TODO (#204) make this error better.
                    f"Getting albums by {self.current_query.type} failed due to the "
                    f"following error\n\n{e}"
                )
                logging.exception("Failed to retrieve albums")
                self.error_dialog.run()
                self.error_dialog.destroy()
                self.error_dialog = None
                self.spinner.hide()
                return

            for c in self.error_container.get_children():
                self.error_container.remove(c)
            if is_partial and (
                len(albums) == 0
                or self.current_query.type != AlbumSearchQuery.Type.RANDOM
            ):
                load_error = LoadError(
                    "Album list",
                    "load albums",
                    has_data=albums is not None and len(albums) > 0,
                    offline_mode=self.offline_mode,
                )
                self.error_container.pack_start(load_error, True, True, 0)
                self.error_container.show_all()
            else:
                self.error_container.hide()

            selected_index = None
            self.current_models = []
            for i, album in enumerate(albums):
                model = AlbumsGrid._AlbumModel(album)

                if model.id == self.currently_selected_id:
                    selected_index = i

                self.current_models.append(model)

            self.emit(
                "num-pages-changed",
                math.ceil(len(self.current_models) / self.page_size),
            )
            do_update_grid(selected_index)

        if force_grid_reload_from_master:
            albums_result = AdapterManager.get_albums(
                self.current_query, use_ground_truth_adapter=use_ground_truth_adapter
            )
            if albums_result.data_is_available:
                # Don't idle add if the data is already available.
                albums_result.add_done_callback(reload_store)
            else:
                self.spinner.show()
                albums_result.add_done_callback(
                    lambda f: GLib.idle_add(reload_store, f)
                )
        else:
            selected_index = None
            for i, album in enumerate(self.current_models):
                if album.id == self.currently_selected_id:
                    selected_index = i
            self.emit(
                "num-pages-changed",
                math.ceil(len(self.current_models) / self.page_size),
            )
            do_update_grid(selected_index)

    # Event Handlers
    # =========================================================================
    def on_child_activated(self, flowbox: Gtk.FlowBox, child: Gtk.Widget):
        click_top = flowbox == self.grid_top
        selected_index = child.get_index()

        if click_top:
            page_offset = self.page_size * self.page
            if self.currently_selected_index is not None and (
                selected_index == self.currently_selected_index - page_offset
            ):
                self.emit("cover-clicked", None)
            else:
                self.emit("cover-clicked", self.list_store_top[selected_index].id)
        else:
            self.emit("cover-clicked", self.list_store_bottom[selected_index].id)

    def on_grid_resize(self, flowbox: Gtk.FlowBox, rect: Gdk.Rectangle):
        # TODO (#124): this doesn't work at all consistency, especially with themes that
        #              add extra padding.
        # 200     + (10      * 2) + (5      * 2) = 230
        # picture + (padding * 2) + (margin * 2)
        new_items_per_row = min((rect.width // 230), 7)
        if new_items_per_row != self.items_per_row:
            self.items_per_row = new_items_per_row
            self.detail_box_inner.set_size_request(self.items_per_row * 230 - 10, -1)

            self.reflow_grids(
                force_reload_from_master=True,
                selected_index=self.currently_selected_index,
            )

    # Helper Methods
    # =========================================================================
    def _make_label(self, text: str, name: str) -> Gtk.Label:
        return Gtk.Label(
            name=name,
            label=text,
            tooltip_text=text,
            ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=22,
            halign=Gtk.Align.START,
        )

    def _create_cover_art_widget(self, item: _AlbumModel) -> Gtk.Box:
        widget_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Cover art image
        artwork = SpinnerImage(
            loading=False,
            image_name="grid-artwork",
            spinner_name="grid-artwork-spinner",
            image_size=200,
        )
        widget_box.pack_start(artwork, False, False, 0)

        # Header for the widget
        header_label = self._make_label(item.album.name, "grid-header-label")
        widget_box.pack_start(header_label, False, False, 0)

        # Extra info for the widget
        info_text = util.dot_join(
            item.album.artist.name if item.album.artist else "-", item.album.year
        )
        if info_text:
            info_label = self._make_label(info_text, "grid-info-label")
            widget_box.pack_start(info_label, False, False, 0)

        # Download the cover art.
        def on_artwork_downloaded(filename: Result[str]):
            artwork.set_from_file(filename.result())
            artwork.set_loading(False)

        cover_art_filename_future = AdapterManager.get_cover_art_uri(
            item.album.cover_art, "file"
        )
        if cover_art_filename_future.data_is_available:
            on_artwork_downloaded(cover_art_filename_future)
        else:
            artwork.set_loading(True)
            cover_art_filename_future.add_done_callback(
                lambda f: GLib.idle_add(on_artwork_downloaded, f)
            )

        widget_box.show_all()
        return widget_box

    def reflow_grids(
        self,
        force_reload_from_master: bool = False,
        selected_index: int = None,
        models: List[_AlbumModel] = None,
    ):
        # Calculate the page that the currently_selected_index is in. If it's a
        # different page, then update the window.
        if selected_index is not None:
            page_of_selected_index = selected_index // self.page_size
            if page_of_selected_index != self.page:
                self.emit(
                    "refresh-window", {"album_page": page_of_selected_index}, False
                )
                return
        page_offset = self.page_size * self.page

        # Calculate the look-at window.
        if models:
            if self.sort_dir == "ascending":
                window = models[page_offset : (page_offset + self.page_size)]
            else:
                reverse_sorted_models = reversed(models)
                # remove to the offset
                for _ in range(page_offset):
                    next(reverse_sorted_models, page_offset)
                window = list(itertools.islice(reverse_sorted_models, self.page_size))
        else:
            window = list(self.list_store_top) + list(self.list_store_bottom)

        # Determine where the cuttoff is between the top and bottom grids.
        entries_before_fold = self.page_size
        if selected_index is not None and self.items_per_row:
            relative_selected_index = selected_index - page_offset
            entries_before_fold = (
                (relative_selected_index // self.items_per_row) + 1
            ) * self.items_per_row

        # Unreveal the current album details first
        if selected_index is None:
            self.detail_box_revealer.set_reveal_child(False)

        if force_reload_from_master:
            # Just remove everything and re-add all of the items. It's not worth trying
            # to diff in this case.
            self.list_store_top.splice(
                0,
                len(self.list_store_top),
                window[:entries_before_fold],
            )
            self.list_store_bottom.splice(
                0,
                len(self.list_store_bottom),
                window[entries_before_fold:],
            )
        elif selected_index or entries_before_fold != self.page_size:
            # This case handles when the selection changes and the entries need to be
            # re-allocated to the top and bottom grids
            # Move entries between the two stores.
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

        if selected_index is not None:
            relative_selected_index = selected_index - page_offset
            to_select = self.grid_top.get_child_at_index(relative_selected_index)
            if not to_select:
                return
            self.grid_top.select_child(to_select)

            if self.currently_selected_index == selected_index:
                return

            for c in self.detail_box_inner.get_children():
                self.detail_box_inner.remove(c)

            model = self.list_store_top[relative_selected_index]
            detail_element = AlbumWithSongs(model.album, cover_art_size=300)
            detail_element.connect(
                "song-clicked",
                lambda _, *args: self.emit("song-clicked", *args),
            )
            detail_element.connect("song-selected", lambda *a: None)

            self.detail_box_inner.pack_start(detail_element, True, True, 0)
            self.detail_box_inner.show_all()
            self.detail_box_revealer.set_reveal_child(True)

            # TODO (#88): scroll so that the grid_top is visible, and the
            # detail_box is visible, with preference to the grid_top. May need
            # to add another flag for this function.
        else:
            self.grid_top.unselect_all()
            self.grid_bottom.unselect_all()

        self.currently_selected_index = selected_index
