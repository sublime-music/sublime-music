import gi
import sys
from datetime import datetime
from typing import List

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk

from libremsonic.server.api_objects import Child, PlaylistWithSongs
from libremsonic.state_manager import ApplicationState
from libremsonic.cache_manager import CacheManager
from libremsonic.ui import util


class PlaylistsPanel(Gtk.Paned):
    """Defines the playlists panel."""
    playlist_ids: List[int] = []
    song_ids: List[int] = []

    def __init__(self):
        Gtk.FlowBox.__init__(
            self,
            orientation=Gtk.Orientation.HORIZONTAL,
        )

        # The playlist list on the left side
        # =====================================================================
        playlist_list_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        playlist_list_actions = Gtk.ActionBar()

        self.new_playlist = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        add_icon = Gio.ThemedIcon(name='list-add')
        image = Gtk.Image.new_from_gicon(add_icon, Gtk.IconSize.LARGE_TOOLBAR)
        box.add(image)
        box.add(Gtk.Label('New Playlist', margin=5))
        self.new_playlist.add(box)
        playlist_list_actions.pack_start(self.new_playlist)

        refresh_button = util.button_with_icon('view-refresh')
        refresh_button.connect('clicked', self.on_list_refresh_click)
        playlist_list_actions.pack_end(refresh_button)

        playlist_list_vbox.add(playlist_list_actions)

        list_scroll_window = Gtk.ScrolledWindow(min_content_width=220)
        self.playlist_list = Gtk.ListBox()
        self.playlist_list.connect('row-activated', self.on_playlist_selected)
        list_scroll_window.add(self.playlist_list)
        playlist_list_vbox.pack_start(list_scroll_window, True, True, 0)

        # Add playlist button

        self.pack1(playlist_list_vbox, False, False)

        # The playlist view on the right side
        # =====================================================================
        playlist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Playlist info panel
        # TODO shrink when playlist is is scrolled down.
        self.info_panel = Gtk.Box(
            name='playlist-info-panel',
            orientation=Gtk.Orientation.HORIZONTAL,
        )
        self.playlist_artwork = Gtk.Image(name='album-artwork')
        self.info_panel.pack_start(self.playlist_artwork, False, False, 0)

        # Name, comment, number of songs, etc.
        playlist_details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        playlist_details_box.pack_start(Gtk.Box(), True, False, 0)

        self.playlist_indicator = self.make_label(name='playlist-indicator')
        playlist_details_box.add(self.playlist_indicator)

        self.playlist_name = self.make_label(name='playlist-name')
        playlist_details_box.add(self.playlist_name)

        self.playlist_comment = self.make_label(name='playlist-comment')
        playlist_details_box.add(self.playlist_comment)

        self.playlist_stats = self.make_label(name='playlist-stats')
        playlist_details_box.add(self.playlist_stats)

        self.info_panel.pack_start(playlist_details_box, True, True, 10)

        playlist_box.pack_start(self.info_panel, False, False, 0)

        # Playlist songs list
        songs_scroll_window = Gtk.ScrolledWindow()
        self.playlist_songs = Gtk.TreeView()
        self.playlist_songs.insert_column_with_attributes(
            -1, 'TITLE', Gtk.CellRendererText())
        self.playlist_songs.insert_column_with_attributes(
            -1, 'ALBUM', Gtk.CellRendererText())
        self.playlist_songs.insert_column_with_attributes(
            -1, 'ARTIST', Gtk.CellRendererText())
        self.playlist_songs.insert_column_with_attributes(
            -1, 'DURATION', Gtk.CellRendererText())
        self.playlist_songs.connect(
            'row-activated', lambda x, y: print('a', x, y))
        songs_scroll_window.add(self.playlist_songs)
        playlist_box.pack_end(songs_scroll_window, True, True, 0)

        self.pack2(playlist_box, True, False)

    # Event Handlers
    # =========================================================================
    def on_playlist_selected(self, playlist_list, row):
        playlist_id = self.playlist_ids[row.get_index()]
        playlist: PlaylistWithSongs = CacheManager.get_playlist(playlist_id)

        # Update the Playlist Info panel
        self.playlist_artwork.set_from_file(
            CacheManager.get_cover_art(playlist.coverArt))
        self.playlist_indicator.set_markup('PLAYLIST')
        self.playlist_name.set_markup(f'<b>{playlist.name}</b>')
        self.playlist_comment.set_text(playlist.comment or '')
        self.playlist_stats.set_markup(self.format_stats(playlist))

        # Update the song list
        self.song_ids = []
        for c in self.playlist_songs.get_children():
            self.playlist_songs.remove(c)

        for song in (playlist.entry or []):
            self.song_ids.append(song.id)
            self.playlist_songs.add(self.create_song_row(song))

        self.playlist_songs.show_all()

    def on_list_refresh_click(self, button):
        self.update_playlist_list(force=True)

    # Helper Methods
    # =========================================================================
    def make_label(self, text=None, name=None, **params):
        return Gtk.Label(text, name=name, halign=Gtk.Align.START, **params)

    def update(self, state: ApplicationState):
        self.update_playlist_list()

    def update_playlist_list(self, force=False):
        self.playlist_ids = []
        for c in self.playlist_list.get_children():
            self.playlist_list.remove(c)

        for playlist in CacheManager.get_playlists(force=force):
            self.playlist_ids.append(playlist.id)
            self.playlist_list.add(self.create_playlist_label(playlist))

        self.playlist_list.show_all()

    def create_playlist_label(self, playlist: PlaylistWithSongs):
        return self.make_label(f'<b>{playlist.name}</b>',
                               use_markup=True,
                               margin=10)

    def create_song_row(self, song: Child):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        title = self.make_label(f'<b>{song.title}</b>',
                                use_markup=True,
                                margin=5)
        box.pack_start(title, True, True, 0)

        album = self.make_label(song.album, margin=5)
        box.pack_start(album, True, True, 0)

        artist = self.make_label(song.artist, margin=5)
        box.pack_start(artist, True, True, 0)

        duration = self.make_label(self.format_song_duration(song.duration),
                                   margin=5)
        box.pack_start(duration, False, True, 0)

        return box

    def pluralize(self, string, number, pluralized_form=None):
        if number != 1:
            return pluralized_form or f'{string}s'
        return string

    def format_stats(self, playlist):
        created_date = playlist.created.strftime('%B %d, %Y')
        return '  •  '.join([
            f'Created by {playlist.owner} on {created_date}',
            '{} {}'.format(playlist.songCount,
                           self.pluralize("song", playlist.songCount)),
            self.format_playlist_duration(playlist.duration)
        ])

    def format_playlist_duration(self, duration_secs) -> str:
        duration_mins = (duration_secs // 60) % 60
        duration_hrs = duration_secs // 60 // 60
        duration_secs = duration_secs % 60

        format_components = []
        if duration_hrs > 0:
            hrs = '{} {}'.format(duration_hrs,
                                 self.pluralize('hour', duration_hrs))
            format_components.append(hrs)

        if duration_mins > 0:
            mins = '{} {}'.format(duration_mins,
                                  self.pluralize('minute', duration_mins))
            format_components.append(mins)

        # Show seconds if there are no hours.
        if duration_hrs == 0:
            secs = '{} {}'.format(duration_secs,
                                  self.pluralize('second', duration_secs))
            format_components.append(secs)

        return ', '.join(format_components)

    def format_song_duration(self, duration_secs) -> str:
        return f'{duration_secs // 60}:{duration_secs % 60:02}'
