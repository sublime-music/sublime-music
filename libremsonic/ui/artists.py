from concurrent.futures import Future
from typing import List, Union

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, Gio, Pango, GLib

from libremsonic.state_manager import ApplicationState
from libremsonic.cache_manager import CacheManager
from libremsonic.ui import util
from libremsonic.ui.common import CoverArtGrid

from libremsonic.server.api_objects import (
    AlbumID3,
    ArtistID3,
    ArtistInfo2,
    ArtistWithAlbumsID3,
    Child,
)

from .albums import AlbumsGrid


class ArtistsPanel(Gtk.Box):
    """Defines the arist panel."""

    __gsignals__ = {
        'song-clicked': (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object),
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, orientation=Gtk.Orientation.VERTICAL, **kwargs)

        self.prev_panel = None

        # Create the stack
        self.stack = Gtk.Stack()
        self.stack.connect('notify::visible-child', self.on_stack_change)
        panels = {
            'grid': ('view-grid-symbolic', ArtistsGrid()),
            'list': ('view-list-symbolic', ArtistList()),
            'artist_detail': (None, ArtistDetailPanel()),
        }

        for name, (icon, child) in panels.items():
            if icon:
                child.connect('item-clicked', self.on_artist_clicked)
                self.stack.add_titled(child, name.lower(), name)
                self.stack.child_set_property(child, 'icon-name', icon)
            else:
                print('ohea')
                self.stack.add_named(child, name)
                child.connect('song-clicked', self.on_song_clicked)

        actionbar = Gtk.ActionBar()

        self.back_button = util.button_with_icon('go-previous-symbolic')
        self.back_button.connect('clicked', self.on_back_button_press)
        actionbar.pack_start(self.back_button)

        self.switcher = Gtk.StackSwitcher(stack=self.stack)
        actionbar.pack_end(self.switcher)

        self.add(actionbar)
        self.add(self.stack)

    def update(self, state: ApplicationState):
        active_panel = self.stack.get_visible_child()
        if hasattr(active_panel, 'update'):
            active_panel.update(state)

        self.update_view_buttons()

    def update_view_buttons(self):
        if self.stack.get_visible_child_name() == 'artist_detail':
            self.back_button.show()
            self.switcher.hide()
        else:
            self.back_button.hide()
            self.switcher.show()

    def button_with_icon(
            self,
            icon_name,
            icon_size=Gtk.IconSize.BUTTON,
            group_with=None,
    ) -> Gtk.RadioButton:
        button = Gtk.RadioButton.new_from_widget(group_with)
        button.set_mode(True)

        icon = Gio.ThemedIcon(name=icon_name)
        image = Gtk.Image.new_from_gicon(icon, icon_size)
        button.add(image)

        return button

    def on_artist_clicked(self, _, artist):
        self.prev_panel = self.stack.get_visible_child_name()
        self.stack.set_visible_child_name('artist_detail')
        self.stack.get_visible_child().update_artist_view(artist.id)

    def on_song_clicked(self, _, song_id, song_queue):
        self.emit('song-clicked', song_id, song_queue)

    def on_stack_change(self, *_):
        self.update_view_buttons()

    def on_back_button_press(self, button):
        self.stack.set_visible_child_name(self.prev_panel or 'grid')


class ArtistModel(GObject.Object):
    def __init__(self, id, name, cover_art, album_count=0):
        self.id = id
        self.name = name
        self.cover_art = cover_art
        self.album_count = album_count
        super().__init__()


class ArtistsGrid(CoverArtGrid):
    """Defines the artists grid."""

    # Override Methods
    # =========================================================================
    def get_header_text(self, item) -> str:
        return item.name

    def get_info_text(self, item) -> str:
        return (str(item.album_count) + ' '
                + util.pluralize('album', item.album_count))

    def get_model_list_future(self, before_download) -> List[ArtistID3]:
        return CacheManager.get_artists(before_download=before_download)

    def create_model_from_element(self, el):
        return ArtistModel(el.id, el.name, el.coverArt, el.albumCount)

    def get_cover_art_filename_future(self, item, before_download) -> Future:
        # TODO convert to get_artist_artwork
        return CacheManager.get_cover_art_filename(
            item.cover_art,
            before_download=before_download,
        )


class ArtistList(Gtk.Paned):
    """Defines the artists list."""

    __gsignals__ = {
        'item-clicked': (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object),
        ),
    }


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

        artwork_overlay = Gtk.Overlay()
        self.artist_artwork = Gtk.Image(name='artist-album-artwork')
        artwork_overlay.add(self.artist_artwork)

        self.artwork_spinner = Gtk.Spinner(name='artist-artwork-spinner',
                                           active=True,
                                           halign=Gtk.Align.CENTER,
                                           valign=Gtk.Align.CENTER)
        artwork_overlay.add_overlay(self.artwork_spinner)
        self.big_info_panel.pack_start(artwork_overlay, False, False, 0)

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

        download_all_button = util.button_with_icon('folder-download-symbolic')
        download_all_button.connect('clicked', self.on_download_all_click)
        self.artist_action_buttons.pack_end(download_all_button, False, False,
                                            5)

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
        before_download=lambda self: self.set_artwork_loading(True),
        on_failure=lambda self, e: print('fail a', e),
    )
    def update_artist_view(self, artist: ArtistWithAlbumsID3):
        self.artist_id = artist.id
        self.artist_indicator.set_text('ARTIST')
        self.artist_name.set_markup(util.esc(f'<b>{artist.name}</b>'))
        self.artist_stats.set_markup(self.format_stats(artist))

        self.update_artist_info(artist.id)
        self.update_artist_artwork(artist)

        self.albums = artist.album
        self.albums_grid.update()

    @util.async_callback(
        lambda *a, **k: CacheManager.get_artist_info2(*a, **k),
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
        before_download=lambda self: self.set_artwork_loading(True),
        on_failure=lambda self, e: self.set_artwork_loading(False),
    )
    def update_artist_artwork(self, cover_art_filename):
        self.artist_artwork.set_from_file(cover_art_filename)
        self.set_artwork_loading(False)

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

    def set_artwork_loading(self, loading_status):
        if loading_status:
            self.artwork_spinner.show()
        else:
            self.artwork_spinner.hide()

    def format_stats(self, artist):
        song_count = sum(a.songCount for a in artist.album)
        duration = sum(a.duration for a in artist.album)
        return util.dot_join(
            '{} {}'.format(artist.albumCount,
                           util.pluralize('album', artist.albumCount)),
            '{} {}'.format(song_count, util.pluralize('song', song_count)),
            util.format_sequence_duration(duration),
        )
