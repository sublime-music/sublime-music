import gi
from typing import List

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, GObject, Pango

from libremsonic.state_manager import ApplicationState
from libremsonic.cache_manager import CacheManager
from libremsonic.ui import util

from libremsonic.server.api_objects import Child


class AlbumsPanel(Gtk.ScrolledWindow):
    __gsignals__ = {
        'song-clicked': (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object),
        ),
    }

    def __init__(self):
        Gtk.ScrolledWindow.__init__(self)
        self.child = AlbumsGrid()
        self.add(self.child)

    def update(self, state: ApplicationState):
        self.child.update(state)


class AlbumModel(GObject.Object):
    def __init__(self, title, cover_art, artist, year):
        self.title = title
        self.cover_art = cover_art
        self.artist = artist
        self.year = year
        super().__init__()


class AlbumsGrid(Gtk.FlowBox):
    # TODO: probably create a sub-class of this for use in both artists and
    # albums. There is honestly not a lot of difference.
    """Defines the albums panel."""

    def __init__(self):
        Gtk.FlowBox.__init__(
            self,
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

        self.albums_model = Gio.ListStore()
        self.bind_model(self.albums_model, self.create_album_widget)

    def update(self, state: ApplicationState):
        # TODO force at an interval
        self.update_grid('random')

    @util.async_callback(
        lambda *a, **k: CacheManager.get_albums(*a, **k),
        before_download=lambda self: print('set loading'),
        on_failure=lambda self, e: print('fail', e),
    )
    def update_grid(self, albums: List[Child]):
        # TODO do the diff thing eventually?
        self.albums_model.remove_all()
        for album in albums:
            self.albums_model.append(
                AlbumModel(
                    album.title,
                    album.coverArt,
                    album.artist,
                    album.year,
                ))

    def create_album_widget(self, item):
        album_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        artwork_overlay = Gtk.Overlay()
        album_artwork = Gtk.Image(name='album-artwork')
        artwork_overlay.add(album_artwork)

        artwork_spinner = Gtk.Spinner(name='album-artwork-spinner',
                                      active=False,
                                      halign=Gtk.Align.CENTER,
                                      valign=Gtk.Align.CENTER)
        artwork_overlay.add_overlay(artwork_spinner)
        album_box.pack_start(artwork_overlay, False, False, 0)

        def artwork_downloaded(f):
            filename = f.result()
            album_artwork.set_from_file(filename)
            artwork_spinner.active = False

        def before_download():
            artwork_spinner.active = True

        cover_art_filename_future = CacheManager.get_cover_art_filename(
            item.cover_art, before_download=before_download)
        cover_art_filename_future.add_done_callback(artwork_downloaded)

        title_label = Gtk.Label(
            name='album-title-label',
            label=item.title,
            tooltip_text=item.title,
            ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=20,
            halign=Gtk.Align.START,
        )
        album_box.pack_start(title_label, False, False, 0)

        info_label = Gtk.Label(
            name='album-info-label',
            label=util.dot_join(item.artist, item.year),
            tooltip_text=util.dot_join(item.artist, item.year),
            ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=20,
            halign=Gtk.Align.START,
        )
        album_box.pack_start(info_label, False, False, 0)

        album_box.show_all()
        return album_box
