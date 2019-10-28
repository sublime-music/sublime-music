import gi
from typing import Optional, Union

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, GLib, Gio, Pango

from sublime.state_manager import ApplicationState
from sublime.cache_manager import CacheManager
from sublime.ui import util
from sublime.ui.common import AlbumWithSongs, IconButton, SpinnerImage

from sublime.server.api_objects import Child, AlbumWithSongsID3

Album = Union[Child, AlbumWithSongsID3]


class AlbumsPanel(Gtk.Box):
    __gsignals__ = {
        'song-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object, object),
        ),
        'refresh-window': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    populating_genre_combo = False

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        actionbar = Gtk.ActionBar()

        # Sort by
        actionbar.add(Gtk.Label(label='Sort'))
        self.sort_type_combo = self.make_combobox(
            (
                ('random', 'randomly'),
                ('byGenre', 'by genre'),
                ('newest', 'by most recently added'),
                ('highest', 'by highest rated'),
                ('frequent', 'by most played'),
                ('recent', 'by most recently played'),
                ('alphabetical', 'alphabetically'),
                ('starred', 'by starred only'),
                ('byYear', 'by year'),
            ),
            self.on_type_combo_changed,
        )
        actionbar.pack_start(self.sort_type_combo)

        # Alphabetically how?
        self.alphabetical_type_combo = self.make_combobox(
            (
                ('name', 'by album name'),
                ('artist', 'by artist name'),
            ),
            self.on_alphabetical_type_change,
        )
        actionbar.pack_start(self.alphabetical_type_combo)

        # Alphabetically how?
        self.genre_combo = self.make_combobox((), self.on_genre_change)
        actionbar.pack_start(self.genre_combo)

        self.from_year_label = Gtk.Label(label='from')
        actionbar.pack_start(self.from_year_label)
        self.from_year_entry = Gtk.Entry()
        self.from_year_entry.connect('changed', self.on_year_changed)
        actionbar.pack_start(self.from_year_entry)

        self.to_year_label = Gtk.Label(label='to')
        actionbar.pack_start(self.to_year_label)
        self.to_year_entry = Gtk.Entry()
        self.to_year_entry.connect('changed', self.on_year_changed)
        actionbar.pack_start(self.to_year_entry)

        refresh = IconButton('view-refresh')
        refresh.connect('clicked', self.on_refresh_clicked)
        actionbar.pack_end(refresh)

        self.add(actionbar)

        scrolled_window = Gtk.ScrolledWindow()
        self.grid = AlbumsGrid()
        self.grid.connect(
            'song-clicked',
            lambda _, *args: self.emit('song-clicked', *args),
        )
        self.grid.connect('cover-clicked', self.on_grid_cover_clicked)
        scrolled_window.add(self.grid)
        self.add(scrolled_window)

    def make_combobox(self, items, on_change):
        store = Gtk.ListStore(str, str)
        for item in items:
            store.append(item)

        combo = Gtk.ComboBox.new_with_model(store)
        combo.set_id_column(0)
        combo.connect('changed', on_change)

        renderer_text = Gtk.CellRendererText()
        combo.pack_start(renderer_text, True)
        combo.add_attribute(renderer_text, 'text', 1)

        return combo

    def populate_genre_combo(
            self,
            state: ApplicationState,
            force: bool = False,
    ):
        if not CacheManager.ready():
            return

        def get_genres_done(f):
            try:
                new_store = [
                    (genre.value, genre.value) for genre in (f.result() or [])
                ]

                util.diff_song_store(self.genre_combo.get_model(), new_store)

                if self.get_id(self.genre_combo) != state.current_album_genre:
                    self.genre_combo.set_active_id(state.current_album_genre)
            finally:
                self.updating_query = False

        # Never force. We invalidate the cache ourselves (force is used when
        # sort params change).
        genres_future = CacheManager.get_genres(force=False)
        genres_future.add_done_callback(
            lambda f: GLib.idle_add(get_genres_done, f))

    def update(self, state: ApplicationState, force: bool = False):
        self.updating_query = True

        self.sort_type_combo.set_active_id(state.current_album_sort)
        self.alphabetical_type_combo.set_active_id(
            state.current_album_alphabetical_sort)
        self.from_year_entry.set_text(str(state.current_album_from_year))
        self.to_year_entry.set_text(str(state.current_album_to_year))
        self.populate_genre_combo(state, force=force)

        # Show/hide the combo boxes.
        def show_if(sort_type, *elements):
            for element in elements:
                if state.current_album_sort == sort_type:
                    element.show()
                else:
                    element.hide()

        show_if('alphabetical', self.alphabetical_type_combo)
        show_if('byGenre', self.genre_combo)
        show_if('byYear', self.from_year_label, self.from_year_entry)
        show_if('byYear', self.to_year_label, self.to_year_entry)

        self.grid.update(
            state=state,
            force=force,
            selected_id=state.selected_album_id,
        )

    def get_id(self, combo):
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            return combo.get_model()[tree_iter][0]

    def on_refresh_clicked(self, button):
        self.emit('refresh-window', {}, True)

    def on_type_combo_changed(self, combo):
        new_active_sort = self.get_id(combo)
        self.grid.update_params(type_=new_active_sort)
        self.emit_if_not_updating(
            'refresh-window',
            {
                'current_album_sort': new_active_sort,
                'selected_album_id': None,
            },
            False,
        )

    def on_alphabetical_type_change(self, combo):
        new_active_alphabetical_sort = self.get_id(combo)
        self.grid.update_params(alphabetical_type=new_active_alphabetical_sort)
        self.emit_if_not_updating(
            'refresh-window',
            {
                'current_album_alphabetical_sort':
                new_active_alphabetical_sort,
                'selected_album_id': None,
            },
            False,
        )

    def on_genre_change(self, combo):
        new_active_genre = self.get_id(combo)
        self.grid.update_params(genre=new_active_genre)
        self.emit_if_not_updating(
            'refresh-window',
            {
                'current_album_genre': new_active_genre,
                'selected_album_id': None,
            },
            True,
        )

    def on_year_changed(self, entry):
        try:
            year = int(entry.get_text())
        except:
            # TODO prevent input of non-numerals
            print('failed, should do something to prevent non-numeric input')
            return

        if self.to_year_entry == entry:
            self.grid.update_params(to_year=year)
            self.emit_if_not_updating(
                'refresh-window',
                {
                    'current_album_to_year': year,
                    'selected_album_id': None,
                },
                True,
            )
        else:
            self.grid.update_params(from_year=year)
            self.emit_if_not_updating(
                'refresh-window',
                {
                    'current_album_from_year': year,
                    'selected_album_id': None,
                },
                True,
            )

    def on_grid_cover_clicked(self, grid, id):
        self.emit(
            'refresh-window',
            {'selected_album_id': id},
            False,
        )

    def emit_if_not_updating(self, *args):
        if self.updating_query:
            return
        self.emit(*args)


class AlbumModel(GObject.Object):
    def __init__(self, album: Album):
        self.album: Album = album
        super().__init__()

    @property
    def id(self):
        return self.album.id

    def __repr__(self):
        return f'<AlbumModel {self.album}>'


class AlbumsGrid(Gtk.Overlay):
    """Defines the albums panel."""
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
    type_: str = None
    alphabetical_type: str = 'name'
    from_year: int = 2010
    to_year: int = 2020
    genre: str = 'Rock'

    current_selection = None
    next_page_fn = None
    parameters_changed = False
    current_min_size_request = 30
    overshoot_update_in_progress = False

    def update_params(
            self,
            type_: str = None,
            alphabetical_type: str = None,
            from_year: int = None,
            to_year: int = None,
            genre: str = None,
    ):
        self.type_ = type_ or self.type_
        self.alphabetical_type = alphabetical_type or self.alphabetical_type
        self.from_year = from_year or self.from_year
        self.to_year = to_year or self.to_year
        self.genre = genre or self.genre
        self.parameters_changed = True
        self.current_min_size_request = 30

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # This is the master list.
        self.list_store = Gio.ListStore()

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

        scrolled_window.add(grid_detail_grid_box)
        self.add(scrolled_window)

        self.spinner = Gtk.Spinner(
            name='grid-spinner',
            active=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        self.add_overlay(self.spinner)

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

    error_dialog = None

    def update_grid(self, force=False, selected_id=None):
        if not CacheManager.ready():
            self.spinner.hide()
            return

        def reflow_grid(force_reload, selected_index):
            selection_changed = (selected_index != self.current_selection)
            self.current_selection = selected_index
            self.reflow_grids(
                force_reload_from_master=force_reload,
                selection_changed=selection_changed,
            )
            self.spinner.hide()
            self.overshoot_update_in_progress = False

        # Calculate the type.
        type_ = self.type_
        if self.type_ == 'alphabetical':
            type_ += {
                'name': 'ByName',
                'artist': 'ByArtist',
            }[self.alphabetical_type]

        require_reflow = self.parameters_changed
        self.parameters_changed = False

        def do_update(f):
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
                    text='Failed to retrieve albums',
                )
                self.error_dialog.format_secondary_markup(
                    f'Getting albums by {type_} failed due to the following error\n\n{e}'
                )
                self.error_dialog.run()
                self.error_dialog.destroy()
                self.error_dialog = None
                self.spinner.hide()
                return

            old_len = len(self.list_store)
            self.list_store.remove_all()

            selected_index = None
            for i, album in enumerate(albums):
                model = AlbumModel(album)

                if model.id == selected_id:
                    selected_index = i

                self.list_store.append(model)

            reflow_grid(
                force or require_reflow or (old_len != len(self.list_store)),
                selected_index,
            )

        future = CacheManager.get_album_list(
            type_=type_,
            from_year=self.from_year,
            to_year=self.to_year,
            genre=self.genre,
            before_download=lambda: GLib.idle_add(self.spinner.show),
            force=force,
        )
        future.add_done_callback(lambda f: GLib.idle_add(do_update, f))

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

    # Helper Methods
    # =========================================================================
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
        header_text = (
            item.album.title if type(item.album) == Child else item.album.name)

        header_label = make_label(header_text, 'grid-header-label')
        widget_box.pack_start(header_label, False, False, 0)

        # Extra info for the widget
        info_text = util.dot_join(item.album.artist, item.album.year)
        if info_text:
            info_label = make_label(info_text, 'grid-info-label')
            widget_box.pack_start(info_label, False, False, 0)

        # Download the cover art.
        def on_artwork_downloaded(f):
            artwork.set_from_file(f.result())
            artwork.set_loading(False)

        def start_loading():
            artwork.set_loading(True)

        cover_art_filename_future = CacheManager.get_cover_art_filename(
            item.album.coverArt,
            before_download=lambda: GLib.idle_add(start_loading),
        )
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
            # TODO make this smarter somehow to avoid flicker. Maybe change
            # this so that it removes one by one and adds back one by one.
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

            self.grid_top.select_child(
                self.grid_top.get_child_at_index(self.current_selection))

            for c in self.detail_box_inner.get_children():
                self.detail_box_inner.remove(c)

            model = self.list_store[self.current_selection]
            detail_element = AlbumWithSongs(model.album, cover_art_size=300)
            detail_element.connect(
                'song-clicked',
                lambda _, song, queue, metadata: self.emit(
                    'song-clicked', song, queue, metadata),
            )
            detail_element.connect('song-selected', lambda *a: None)

            self.detail_box_inner.pack_start(detail_element, True, True, 0)
            self.detail_box.show_all()

            # TODO scroll so that the grid_top is visible, and the detail_box
            # is visible, with preference to the grid_top. May need to add
            # another flag for this function.
        else:
            self.grid_top.unselect_all()
            self.detail_box.hide()
