import gi
from typing import Optional, Union

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, GObject

from libremsonic.state_manager import ApplicationState
from libremsonic.cache_manager import CacheManager
from libremsonic.ui import util
from libremsonic.ui.common import AlbumWithSongs, CoverArtGrid

from libremsonic.server.api_objects import Child, AlbumWithSongsID3

Album = Union[Child, AlbumWithSongsID3]


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
        self.child.connect(
            'song-clicked',
            lambda _, song, queue: self.emit('song-clicked', song, queue),
        )
        self.add(self.child)

    def update(self, state: ApplicationState):
        self.child.update(state)


class AlbumModel(GObject.Object):
    def __init__(self, album: Album):
        self.album: Album = album
        super().__init__()

    def __repr__(self):
        return f'<AlbumModel {self.album}>'


class AlbumsGrid(CoverArtGrid):
    """Defines the albums panel."""

    # Override Methods
    # =========================================================================
    def get_header_text(self, item: AlbumModel) -> str:
        return (item.album.title
                if type(item.album) == Child else item.album.name)

    def get_info_text(self, item: AlbumModel) -> Optional[str]:
        return util.dot_join(item.album.artist, item.album.year)

    def get_model_list_future(self, before_download):
        return CacheManager.get_albums(
            type_='random',
            before_download=before_download,
        )

    def create_model_from_element(self, album):
        return AlbumModel(album)

    def create_detail_element_from_model(self, album: AlbumModel):
        return AlbumWithSongs(album.album)

    def get_cover_art_filename_future(self, item, before_download):
        return CacheManager.get_cover_art_filename(
            item.album.coverArt,
            before_download=before_download,
        )
