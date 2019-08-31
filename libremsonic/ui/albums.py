import gi
from typing import Optional, Union

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, GLib

from libremsonic.state_manager import ApplicationState
from libremsonic.cache_manager import CacheManager
from libremsonic.ui import util
from libremsonic.ui.common import AlbumWithSongs, IconButton, CoverArtGrid

from libremsonic.server.api_objects import Child, AlbumWithSongsID3

Album = Union[Child, AlbumWithSongsID3]


class AlbumsPanel(Gtk.Box):
    __gsignals__ = {
        'song-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object, object),
        ),
    }

    currently_active_sort: str = 'random'
    currently_active_alphabetical_sort: str = 'name'
    currently_active_genre: str = 'Rock'
    currently_active_from_year: int = 2010
    currently_active_to_year: int = 2020

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
        self.genre_combo = self.make_combobox(
            (),
            self.on_genre_change,
        )
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
        refresh.connect('clicked', lambda *a: self.update(force=True))
        actionbar.pack_end(refresh)

        self.add(actionbar)

        scrolled_window = Gtk.ScrolledWindow()
        self.grid = AlbumsGrid()
        self.grid.connect(
            'song-clicked',
            lambda _, song, queue, metadata: self.emit('song-clicked', song,
                                                       queue, metadata),
        )
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

    def populate_genre_combo(self):
        def get_genres_done(f):
            model = self.genre_combo.get_model()

            self.populating_genre_combo = True
            model.clear()
            for genre in (f.result() or []):
                model.append((genre.value, genre.value))

            self.populating_genre_combo = False
            self.genre_combo.set_active_id(self.currently_active_genre)

        genres_future = CacheManager.get_genres()
        genres_future.add_done_callback(
            lambda f: GLib.idle_add(get_genres_done, f))

    def update(self, state: ApplicationState = None, force: bool = False):
        # TODO store this in state
        self.sort_type_combo.set_active_id(self.currently_active_sort)
        self.alphabetical_type_combo.set_active_id(
            self.currently_active_alphabetical_sort)
        self.from_year_entry.set_text(str(self.currently_active_from_year))
        self.to_year_entry.set_text(str(self.currently_active_to_year))

        self.populate_genre_combo()

        # Show/hide the combo boxes.
        def show_if(sort_type, *elements):
            for element in elements:
                if self.currently_active_sort == sort_type:
                    element.show()
                else:
                    element.hide()

        show_if('alphabetical', self.alphabetical_type_combo)
        show_if('byGenre', self.genre_combo)
        show_if('byYear', self.from_year_label, self.from_year_entry)
        show_if('byYear', self.to_year_label, self.to_year_entry)

        self.grid.update(state=state, force=force)

    def get_id(self, combo):
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            return combo.get_model()[tree_iter][0]

    def on_type_combo_changed(self, combo):
        self.currently_active_sort = self.get_id(combo)
        if self.grid.type_ != self.currently_active_sort:
            self.grid.update_params(type_=self.currently_active_sort)
            self.update(force=True)

    def on_alphabetical_type_change(self, combo):
        self.currently_active_alphabetical_sort = self.get_id(combo)
        if self.grid.alphabetical_type != self.currently_active_alphabetical_sort:
            self.grid.update_params(
                alphabetical_type=self.currently_active_alphabetical_sort)
            self.update(force=True)

    def on_genre_change(self, combo):
        if self.populating_genre_combo:
            return
        self.currently_active_genre = self.get_id(combo)
        if self.grid.genre != self.currently_active_genre:
            self.grid.update_params(genre=self.currently_active_genre)
            self.update(force=True)

    def on_year_changed(self, entry):
        try:
            year = int(entry.get_text())
        except:
            print('failed, should do something to prevent non-numeric input')
            return

        if self.to_year_entry == entry:
            self.currently_active_to_year = year
            if self.grid.to_year != self.currently_active_to_year:
                self.grid.update_params(to_year=year)
                self.update(force=True)
        else:
            self.currently_active_from_year = year
            if self.grid.from_year != self.currently_active_from_year:
                self.grid.update_params(from_year=year)
                self.update(force=True)


class AlbumModel(GObject.Object):
    def __init__(self, album: Album):
        self.album: Album = album
        super().__init__()

    def __repr__(self):
        return f'<AlbumModel {self.album}>'


class AlbumsGrid(CoverArtGrid):
    """Defines the albums panel."""
    type_: str = 'random'
    alphabetical_type: str = 'name'
    from_year: int = 2010
    to_year: int = 2020
    genre: str = 'Rock'

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

    # Override Methods
    # =========================================================================
    def get_header_text(self, item: AlbumModel) -> str:
        return (item.album.title
                if type(item.album) == Child else item.album.name)

    def get_info_text(self, item: AlbumModel) -> Optional[str]:
        return util.dot_join(item.album.artist, item.album.year)

    def get_model_list_future(self, before_download, force=False):
        type_ = self.type_
        if self.type_ == 'alphabetical':
            type_ += {
                'name': 'ByName',
                'artist': 'ByArtist',
            }[self.alphabetical_type]

        return CacheManager.get_albums(
            type_=type_,
            to_year=self.to_year,
            from_year=self.from_year,
            genre=self.genre,
            before_download=before_download,
            force=force,
        )

    def create_model_from_element(self, album):
        return AlbumModel(album)

    def create_detail_element_from_model(self, album: AlbumModel):
        return AlbumWithSongs(album.album, cover_art_size=300)

    def get_cover_art_filename_future(self, item, before_download):
        return CacheManager.get_cover_art_filename(
            item.album.coverArt,
            before_download=before_download,
        )
