from typing import List

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, Gio, Pango, GLib

from libremsonic.state_manager import ApplicationState
from libremsonic.cache_manager import CacheManager
from libremsonic.ui import util

from libremsonic.server.api_objects import (
    ArtistID3,
    ArtistInfo2,
    ArtistWithAlbumsID3,
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
                child.connect('artist-clicked', self.on_artist_clicked)
                self.stack.add_titled(child, name.lower(), name)
                self.stack.child_set_property(child, 'icon-name', icon)
            else:
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

    def on_artist_clicked(self, _, artist_id):
        self.prev_panel = self.stack.get_visible_child_name()
        self.stack.set_visible_child_name('artist_detail')
        self.stack.get_visible_child().update_artist_view(artist_id)

    def on_song_clicked(self, _, song_id, song_queue):
        self.emit('song-clicked', song_id, song_queue)

    def on_stack_change(self, *_):
        self.update_view_buttons()

    def on_back_button_press(self, button):
        self.stack.set_visible_child_name(self.prev_panel or 'grid')


class ArtistModel(GObject.Object):
    def __init__(self, artist_id, name, cover_art, album_count=0):
        self.artist_id = artist_id
        self.name = name
        self.cover_art = cover_art
        self.album_count = album_count
        super().__init__()


class ArtistsGrid(Gtk.ScrolledWindow):
    """Defines the artists grid."""
    __gsignals__ = {
        'artist-clicked': (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (str, ),
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grid = Gtk.FlowBox(
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
        self.grid.connect('child-activated', self.on_child_activated)

        self.artists_model = Gio.ListStore()
        self.grid.bind_model(self.artists_model, self.create_artist_widget)
        self.add(self.grid)

    def update(self, state: ApplicationState):
        self.update_grid()

    @util.async_callback(
        lambda *a, **k: CacheManager.get_artists(*a, **k),
        before_download=lambda self: print('set loading'),
        on_failure=lambda self, e: print('fail', e),
    )
    def update_grid(self, artists: List[ArtistID3]):
        # TODO do the diff thing eventually?
        self.artists_model.remove_all()
        for artist in artists:
            self.artists_model.append(
                ArtistModel(
                    artist.id,
                    artist.name,
                    artist.coverArt,
                    artist.albumCount,
                ))

    # Event Handlers
    # =========================================================================
    def on_child_activated(self, flowbox, child):
        self.emit('artist-clicked',
                  self.artists_model[child.get_index()].artist_id)

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

        name_label = Gtk.Label(
            name='artist-name-label',
            label=item.name,
            tooltip_text=item.name,
            ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=20,
            halign=Gtk.Align.START,
        )
        artist_box.pack_start(name_label, False, False, 0)

        info_text = (str(item.album_count) + ' ' +
                     util.pluralize('album', item.album_count))
        info_label = Gtk.Label(
            name='artist-info-label',
            label=info_text,
            tooltip_text=info_text,
            ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=20,
            halign=Gtk.Align.START,
        )
        artist_box.pack_start(info_label, False, False, 0)

        def artwork_downloaded(f):
            filename = f.result()
            artist_artwork.set_from_file(filename)
            artwork_spinner.active = False

        def before_download():
            artwork_spinner.active = True

        cover_art_filename_future = CacheManager.get_cover_art_filename(
            item.cover_art, before_download=before_download)
        cover_art_filename_future.add_done_callback(artwork_downloaded)

        artist_box.show_all()
        return artist_box


class ArtistList(Gtk.Paned):
    """Defines the artists list."""
    __gsignals__ = {
        'artist-clicked': (
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

        self.artist_stats = self.make_label(name='artist-stats')
        artist_details_box.add(self.artist_stats)

        self.big_info_panel.pack_start(artist_details_box, True, True, 10)

        artist_info_box.pack_start(self.big_info_panel, False, True, 0)

        albums_grid = AlbumsGrid()
        albums_grid_scrolled_window = Gtk.ScrolledWindow()
        albums_grid_scrolled_window.add(albums_grid)
        artist_info_box.pack_start(albums_grid_scrolled_window, True, True, 0)

        self.add(artist_info_box)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_artist(*a, **k),
        before_download=lambda self: self.set_artwork_loading(True),
        on_failure=lambda self, e: print('fail a', e),
    )
    def update_artist_view(self, artist: ArtistWithAlbumsID3):
        self.artist_indicator.set_text('ARTIST')
        self.artist_name.set_markup(util.esc(f'<b>{artist.name}</b>'))
        self.artist_stats.set_markup(self.format_stats(artist))

        self.update_artist_info(artist.id)
        self.update_artist_artwork(artist)

        # self.update_playlist_song_list(playlist.id)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_artist_info2(*a, **k),
    )
    def update_artist_info(self, artist_info: ArtistInfo2):
        self.artist_bio.set_markup(util.esc(''.join(artist_info.biography)))

    # TODO combine these two sources and prefer artist info version.
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
        print('refresh')

    def on_download_all_click(self, *args):
        print('download all')

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
