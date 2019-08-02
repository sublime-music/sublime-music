from concurrent.futures import Future
from typing import List, Union, Optional

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, Gio

from libremsonic.state_manager import ApplicationState
from libremsonic.cache_manager import CacheManager
from libremsonic.ui import util
from libremsonic.ui.common import CoverArtGrid, SpinnerImage

from libremsonic.server.api_objects import (
    AlbumID3,
    ArtistID3,
    ArtistInfo2,
    ArtistWithAlbumsID3,
    Child,
)

from .albums import AlbumsGrid


class ArtistsPanel(Gtk.Paned):
    """Defines the arist panel."""

    __gsignals__ = {
        'song-clicked': (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object),
        ),
    }

    def __init__(self, *args, **kwargs):
        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)

        # self.pack1(playlist_list_vbox, False, False)
        self.pack2(ArtistDetailPanel(), True, False)

    def update(self, state: ApplicationState):
        pass


class ArtistModel(GObject.Object):
    def __init__(self, id, name, cover_art, album_count=0):
        self.id = id
        self.name = name
        self.cover_art = cover_art
        self.album_count = album_count
        super().__init__()


class ArtistDetailPanel(Gtk.Box):
    """Defines the artists list."""

    __gsignals__ = {
        'song-clicked': (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object),
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            orientation=Gtk.Orientation.VERTICAL,
            name='artist-detail-panel',
            **kwargs,
        )
        self.albums: Union[List[AlbumID3], List[Child]] = []
        self.artist_id = None

        artist_info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Artist info panel
        self.big_info_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.artist_artwork = SpinnerImage(
            loading=False,
            image_name='artist-album-artwork',
            spinner_name='artist-artwork-spinner',
        )
        self.big_info_panel.pack_start(self.artist_artwork, False, False, 0)

        # Action buttons, name, comment, number of songs, etc.
        artist_details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Action buttons (note we are packing end here, so we have to put them
        # in right-to-left).
        self.artist_action_buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL)

        view_refresh_button = util.button_with_icon('view-refresh-symbolic')
        view_refresh_button.connect('clicked', self.on_view_refresh_click)
        self.artist_action_buttons.pack_end(view_refresh_button, False, False,
                                            5)

        download_all_btn = util.button_with_icon('folder-download-symbolic')
        download_all_btn.connect('clicked', self.on_download_all_click)
        self.artist_action_buttons.pack_end(download_all_btn, False, False, 5)

        artist_details_box.pack_start(self.artist_action_buttons, False, False,
                                      5)

        artist_details_box.pack_start(Gtk.Box(), True, False, 0)

        self.artist_indicator = self.make_label(name='artist-indicator')
        artist_details_box.add(self.artist_indicator)

        self.artist_name = self.make_label(name='artist-name')
        artist_details_box.add(self.artist_name)

        self.artist_bio = self.make_label(name='artist-bio',
                                          max_width_chars=80,
                                          justify=Gtk.Justification.LEFT)
        self.artist_bio.set_line_wrap(True)
        artist_details_box.add(self.artist_bio)

        self.similar_artists_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL)

        self.similar_artists_label = self.make_label(name='similar-artists')
        self.similar_artists_box.add(self.similar_artists_label)

        self.similar_artists_button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL)
        self.similar_artists_box.add(self.similar_artists_button_box)

        artist_details_box.add(self.similar_artists_box)

        self.artist_stats = self.make_label(name='artist-stats')
        artist_details_box.add(self.artist_stats)

        self.big_info_panel.pack_start(artist_details_box, True, True, 10)

        artist_info_box.pack_start(self.big_info_panel, False, True, 0)

        self.albums_grid = AlbumsGrid()
        self.albums_grid.grid.set_halign(Gtk.Align.START)
        self.albums_grid.get_model_list_future = self.get_model_list_future
        artist_info_box.pack_start(self.albums_grid, True, True, 0)

        self.add(artist_info_box)

    def get_model_list_future(self, before_download):
        def do_get_model_list() -> List[Child]:
            return self.albums

        return CacheManager.executor.submit(do_get_model_list)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_artist(*a, **k),
        before_download=lambda self: self.artist_artwork.set_loading(True),
        on_failure=lambda self, e: print('fail a', e),
    )
    def update_artist_view(self, artist: ArtistWithAlbumsID3):
        self.artist_id = artist.id
        self.artist_indicator.set_text('ARTIST')
        self.artist_name.set_markup(util.esc(f'<b>{artist.name}</b>'))
        self.artist_stats.set_markup(self.format_stats(artist))

        self.update_artist_info(artist.id)
        self.update_artist_artwork(artist)

        self.albums = artist.get('album', artist.get('child', []))
        self.albums_grid.update()

    @util.async_callback(
        lambda *a, **k: CacheManager.get_artist_info(*a, **k),
    )
    def update_artist_info(self, artist_info: ArtistInfo2):
        self.artist_bio.set_markup(util.esc(''.join(artist_info.biography)))

        if len(artist_info.similarArtist or []) > 0:
            self.similar_artists_label.set_markup('<b>Similar Artists:</b> ')
            for c in self.similar_artists_button_box.get_children():
                self.similar_artists_button_box.remove(c)

            for artist in artist_info.similarArtist[:5]:
                self.similar_artists_button_box.add(
                    Gtk.LinkButton(
                        uri=f'artist://{artist.id}',
                        label=artist.name,
                        name='similar-artist-button',
                    ))
            self.similar_artists_box.show_all()
        else:
            self.similar_artists_box.hide()

    @util.async_callback(
        lambda *a, **k: CacheManager.get_artist_artwork(*a, **k),
        before_download=lambda self: self.artist_artwork.set_loading(True),
        on_failure=lambda self, e: self.artist_artwork.set_loading(False),
    )
    def update_artist_artwork(self, cover_art_filename):
        self.artist_artwork.set_from_file(cover_art_filename)
        self.artist_artwork.set_loading(False)

    # Event Handlers
    # =========================================================================
    def on_view_refresh_click(self, *args):
        self.update_artist_view(self.artist_id, force=True)

    def on_download_all_click(self, btn):
        print('download all')
        artist = CacheManager.get_artist(self.artist_id).result()
        for album in artist.album:
            print(album)

    # Helper Methods
    # =========================================================================
    def make_label(self, text=None, name=None, **params):
        return Gtk.Label(
            label=text,
            name=name,
            halign=Gtk.Align.START,
            **params,
        )

    def format_stats(self, artist):
        album_count = artist.get('albumCount', len(artist.get('child', [])))
        components = [
            '{} {}'.format(album_count, util.pluralize('album', album_count)),
        ]

        if artist.get('album'):
            song_count = sum(a.songCount for a in artist.album)
            duration = sum(a.duration for a in artist.album)
            components += [
                '{} {}'.format(song_count, util.pluralize('song', song_count)),
                util.format_sequence_duration(duration),
            ]
        elif artist.get('child'):
            plays = sum(c.playCount for c in artist.child)
            components += [
                '{} {}'.format(plays, util.pluralize('play', plays)),
            ]

        return util.dot_join(*components)
