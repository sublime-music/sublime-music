from typing import List

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, Gio, Pango

from libremsonic.state_manager import ApplicationState
from libremsonic.cache_manager import CacheManager
from libremsonic.ui import util

from libremsonic.server.api_objects import ArtistID3


class ArtistsPanel(Gtk.ScrolledWindow):
    __gsignals__ = {
        'song-clicked': (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object),
        ),
    }

    def __init__(self):
        Gtk.ScrolledWindow.__init__(self)
        self.child = ArtistsGrid()
        self.add(self.child)

    def update(self, state: ApplicationState):
        self.child.update(state)


class ArtistModel(GObject.Object):
    def __init__(self, name, cover_art):
        self.name = name
        self.cover_art = cover_art
        super().__init__()


class ArtistsGrid(Gtk.FlowBox):
    """Defines the artists panel."""

    def __init__(self):
        Gtk.FlowBox.__init__(
            self,
            vexpand=True,
            hexpand=True,
            row_spacing=10,
            column_spacing=10,
            margin_top=12,
            margin_bottom=12,
            homogeneous=True,
            valign=Gtk.Align.START,
            halign=Gtk.Align.CENTER,
            selection_mode=Gtk.SelectionMode.BROWSE,
        )

        self.artist_model = Gio.ListStore()

        self.bind_model(self.artist_model, self.create_artist_widget)

    def update(self, state: ApplicationState):
        self.update_grid()

    @util.async_callback(
        lambda *a, **k: CacheManager.get_artists(*a, **k),
        before_download=lambda self: print('ohea'),
        on_failure=lambda self, e: print('fail', e),
    )
    def update_grid(self, artists: List[ArtistID3]):
        # TODO do the diff thing eventually?
        self.artist_model.remove_all()
        for artist in artists:
            self.artist_model.append(ArtistModel(artist.name, artist.coverArt))

    def create_artist_widget(self, item):
        artist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        artwork_overlay = Gtk.Overlay()
        artist_artwork = Gtk.Image(name='artist-artwork')
        artwork_overlay.add(artist_artwork)

        artwork_spinner = Gtk.Spinner(name='artist-artwork-spinner',
                                      active=False,
                                      halign=Gtk.Align.CENTER,
                                      valign=Gtk.Align.CENTER)
        artwork_overlay.add_overlay(artwork_spinner)
        artist_box.pack_start(artwork_overlay, False, False, 0)

        def artwork_downloaded(f):
            filename = f.result()
            artist_artwork.set_from_file(filename)
            artwork_spinner.active = False

        def before_download():
            artwork_spinner.active = True

        cover_art_filename_future = CacheManager.get_cover_art_filename(
            item.cover_art, before_download=before_download)
        cover_art_filename_future.add_done_callback(artwork_downloaded)

        name_label = Gtk.Label(
            name='artist-name-label',
            label=item.name,
            ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=20,
        )

        artist_box.pack_end(name_label, False, False, 0)
        artist_box.show_all()
        return artist_box

    @util.async_callback(
        lambda *a, **k: CacheManager.get_cover_art_filename(*a, **k),
        before_download=lambda self: self.set_playlist_art_loading(True),
        on_failure=lambda self, e: self.set_playlist_art_loading(False),
    )
    def update_playlist_artwork(self, cover_art_filename):
        self.playlist_artwork.set_from_file(cover_art_filename)
        self.set_playlist_art_loading(False)
