import gi
from typing import Optional

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, GObject, Pango

from libremsonic.state_manager import ApplicationState
from libremsonic.cache_manager import CacheManager
from libremsonic.ui import util
from libremsonic.ui.common import CoverArtGrid

from libremsonic.server.api_objects import Child


class AlbumsPanel(Gtk.ScrolledWindow):
    __gsignals__ = {
        'song-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object),
        ),
    }

    def __init__(self):
        Gtk.ScrolledWindow.__init__(self)
        self.child = AlbumsGrid()
        self.child.connect('song-clicked', self.on_song_clicked)
        self.add(self.child)

    def update(self, state: ApplicationState):
        self.child.update(state)

    def on_song_clicked(self, *args):
        print('song clicked')
        print(args)


class AlbumModel(GObject.Object):
    def __init__(self, title, cover_art, artist, year):
        self.title = title
        self.cover_art = cover_art
        self.artist = artist
        self.year = year
        super().__init__()

    def __repr__(self):
        return f'<AlbumModel title={self.title} cover_art={self.cover_art} artist={self.artist} year={self.year}>'


class AlbumsGrid(CoverArtGrid):
    """Defines the albums panel."""

    # Override Methods
    # =========================================================================
    def get_header_text(self, item: AlbumModel) -> str:
        return item.title

    def get_info_text(self, item: AlbumModel) -> Optional[str]:
        return util.dot_join(item.artist, item.year)

    def get_model_list_future(self, before_download):
        return CacheManager.get_albums(
            type_='random',
            before_download=before_download,
        )

    def create_model_from_element(self, album):
        return AlbumModel(
            album.title if type(album) == Child else album.name,
            album.coverArt,
            album.artist,
            album.year,
        )

    def get_cover_art_filename_future(self, item, before_download):
        return CacheManager.get_cover_art_filename(
            item.cover_art,
            before_download=before_download,
        )
