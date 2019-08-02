from concurrent.futures import Future
from typing import List, Union, Optional

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, Pango

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


class ArtistModel(GObject.Object):
    def __init__(self, id, name, cover_art, album_count=0):
        self.id = id
        self.name = name
        self.cover_art = cover_art
        self.album_count = album_count
        super().__init__()


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

        self.selected_artist = None

        self.artist_list = ArtistList()
        self.artist_list.connect('selection-changed',
                                 self.on_list_selection_changed)
        self.pack1(self.artist_list, False, False)

        self.artist_detail_panel = ArtistDetailPanel()
        self.pack2(self.artist_detail_panel, True, False)

    def update(self, state: ApplicationState):
        self.artist_list.update()
        # self.artist_detail_panel.update()

    def on_list_selection_changed(self, artist_list, artist):
        self.artist_detail_panel.update_artist_view(artist.id)


class ArtistList(Gtk.Box):
    __gsignals__ = {
        'selection-changed': (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (object, ),
        ),
    }

    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        self.artist_map = {}

        list_actions = Gtk.ActionBar()

        refresh = util.button_with_icon('view-refresh')
        refresh.connect('clicked', lambda *a: self.update(force=True))
        list_actions.pack_end(refresh)

        self.add(list_actions)

        list_scroll_window = Gtk.ScrolledWindow(min_content_width=250)
        self.list = Gtk.ListBox(name='artist-list-listbox')

        self.loading_indicator = Gtk.ListBoxRow(
            activatable=False,
            selectable=False,
        )
        loading_spinner = Gtk.Spinner(name='artist-list-spinner', active=True)
        self.loading_indicator.add(loading_spinner)
        self.list.add(self.loading_indicator)

        self.list.connect('row-activated', self.on_row_activated)
        list_scroll_window.add(self.list)
        self.pack_start(list_scroll_window, True, True, 0)

    def update(self, force=False):
        self.update_list(force=force)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_artists(*a, **k),
        before_download=lambda self: self.loading_indicator.show(),
        on_failure=lambda self, e: self.loading_indicator.hide(),
    )
    def update_list(self, artists):
        selected_row = self.list.get_selected_row()
        selected_artist = None
        if selected_row:
            selected_artist = self.artist_map.get(selected_row.get_index())

        # Remove everything
        for row in self.list.get_children()[1:]:
            self.list.remove(row)
        self.playlist_map = {}
        selected_idx = None

        for i, artist in enumerate(artists):
            # Use i + 1 because of the loading indicator in index 0.
            if selected_artist and artist.id == selected_artist.id:
                selected_idx = i + 1
            self.artist_map[i + 1] = artist

            label_text = [f'<b>{util.esc(artist.name)}</b>']

            album_count = artist.get('albumCount')
            if album_count:
                label_text.append('{} {}'.format(
                    album_count, util.pluralize('album', album_count)))

            self.list.add(
                Gtk.Label(
                    label='\n'.join(label_text),
                    use_markup=True,
                    margin=12,
                    halign=Gtk.Align.START,
                    ellipsize=Pango.EllipsizeMode.END,
                    max_width_chars=30,
                ))
        if selected_idx:
            row = self.list.get_row_at_index(selected_idx)
            self.list.select_row(row)

        self.list.show_all()
        self.loading_indicator.hide()

    def on_row_activated(self, listbox, row):
        self.emit('selection-changed', self.artist_map[row.get_index()])


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
