import gi
from pathlib import Path
from typing import List

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, Pango, GObject, GLib

from libremsonic.server.api_objects import Child, PlaylistWithSongs
from libremsonic.state_manager import ApplicationState
from libremsonic.cache_manager import CacheManager, SongCacheStatus
from libremsonic.ui import util


class PlaylistsPanel(Gtk.Paned):
    """Defines the playlists panel."""
    __gsignals__ = {
        'song-clicked': (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object),
        ),
    }

    playlist_ids: List[str] = []
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
        self.playlist_list = Gtk.ListBox(name='playlist-list-listbox')

        self.playlist_list_loading = Gtk.Spinner(name='playlist-list-spinner',
                                                 active=True)
        self.playlist_list.add(self.playlist_list_loading)

        self.playlist_list.connect('row-activated', self.on_playlist_selected)
        list_scroll_window.add(self.playlist_list)
        playlist_list_vbox.pack_start(list_scroll_window, True, True, 0)

        # Add playlist button

        self.pack1(playlist_list_vbox, False, False)

        # The playlist view on the right side
        # =====================================================================
        loading_overlay = Gtk.Overlay(name='playlist-view-overlay')
        playlist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Playlist info panel
        # TODO shrink when playlist is is scrolled down.
        self.big_info_panel = Gtk.Box(
            name='playlist-info-panel',
            orientation=Gtk.Orientation.HORIZONTAL,
        )

        artwork_overlay = Gtk.Overlay()
        self.playlist_artwork = Gtk.Image(name='playlist-album-artwork')
        artwork_overlay.add(self.playlist_artwork)

        self.artwork_spinner = Gtk.Spinner(name='playlist-artwork-spinner',
                                           active=True,
                                           halign=Gtk.Align.CENTER,
                                           valign=Gtk.Align.CENTER)
        artwork_overlay.add_overlay(self.artwork_spinner)
        self.big_info_panel.pack_start(artwork_overlay, False, False, 0)

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

        self.big_info_panel.pack_start(playlist_details_box, True, True, 10)

        playlist_box.pack_start(self.big_info_panel, False, True, 0)

        # Playlist songs list
        playlist_view_scroll_window = Gtk.ScrolledWindow()

        def create_column(header, text_idx, bold=False, align=0, width=None):
            renderer = Gtk.CellRendererText(
                xalign=align,
                weight=Pango.Weight.BOLD if bold else Pango.Weight.NORMAL,
                ellipsize=Pango.EllipsizeMode.END,
            )
            renderer.set_fixed_size(width or -1, 35)

            column = Gtk.TreeViewColumn(header, renderer, text=text_idx)
            column.set_resizable(True)
            column.set_expand(not width)
            return column

        self.playlist_song_model = Gtk.ListStore(
            str,  # cache status
            str,  # title
            str,  # album
            str,  # artist
            str,  # duration
            str,  # song ID
        )

        self.playlist_songs = Gtk.TreeView(model=self.playlist_song_model,
                                           margin_top=15)

        # Song status column.
        renderer = Gtk.CellRendererPixbuf()
        renderer.set_fixed_size(30, 35)

        column = Gtk.TreeViewColumn('', renderer, icon_name=0)
        column.set_resizable(True)
        self.playlist_songs.append_column(column)

        self.playlist_songs.append_column(create_column('TITLE', 1, bold=True))
        self.playlist_songs.append_column(create_column('ALBUM', 2))
        self.playlist_songs.append_column(create_column('ARTIST', 3))
        self.playlist_songs.append_column(
            create_column('DURATION', 4, align=1, width=40))

        self.playlist_songs.connect('row-activated', self.on_song_double_click)
        playlist_view_scroll_window.add(self.playlist_songs)

        playlist_box.pack_end(playlist_view_scroll_window, True, True, 0)
        loading_overlay.add(playlist_box)

        playlist_view_spinner = Gtk.Spinner(active=True)
        playlist_view_spinner.start()

        self.playlist_view_loading_box = Gtk.Alignment(
            name='playlist-view-overlay',
            xalign=0.5,
            yalign=0.5,
            xscale=0.1,
            yscale=0.1)
        self.playlist_view_loading_box.add(playlist_view_spinner)
        loading_overlay.add_overlay(self.playlist_view_loading_box)

        self.pack2(loading_overlay, True, False)

    # Event Handlers
    # =========================================================================
    def on_playlist_selected(self, playlist_list, row):
        # Use row index - 1 due to the loading indicator.
        playlist_id = self.playlist_ids[row.get_index() - 1]
        self.update_playlist_view(playlist_id)

    def on_list_refresh_click(self, button):
        # TODO: this should reselect the selected playlist. If the playlist no
        # longer exists, it should also update the playlist view on the right.
        self.update_playlist_list(force=True)

    def on_song_double_click(self, treeview, idx, column):
        # The song ID is in the last column of the model.
        song_id = self.playlist_song_model[idx][-1]
        self.emit('song-clicked', song_id,
                  [m[-1] for m in self.playlist_song_model])

    # Helper Methods
    # =========================================================================
    def make_label(self, text=None, name=None, **params):
        return Gtk.Label(text, name=name, halign=Gtk.Align.START, **params)

    def update(self, state: ApplicationState):
        self.set_playlist_view_loading(False)
        self.set_playlist_art_loading(False)
        self.update_playlist_list()
        selected = self.playlist_list.get_selected_row()
        if selected:
            playlist_id = self.playlist_ids[selected.get_index() - 1]
            self.update_playlist_view(playlist_id)

    def set_playlist_list_loading(self, loading_status):
        if loading_status:
            self.playlist_list_loading.show()
        else:
            self.playlist_list_loading.hide()

    def set_playlist_view_loading(self, loading_status):
        if loading_status:
            self.playlist_view_loading_box.show()
            self.artwork_spinner.show()
        else:
            self.playlist_view_loading_box.hide()

    def set_playlist_art_loading(self, loading_status):
        if loading_status:
            self.artwork_spinner.show()
        else:
            self.artwork_spinner.hide()

    @util.async_callback(
        lambda *a, **k: CacheManager.get_playlists(*a, **k),
        before_fn=lambda self: self.set_playlist_list_loading(True),
    )
    def update_playlist_list(self, playlists: List[PlaylistWithSongs]):
        not_seen = set(self.playlist_ids)

        for playlist in playlists:
            if playlist.id not in self.playlist_ids:
                self.playlist_ids.append(playlist.id)
                self.playlist_list.add(self.create_playlist_label(playlist))
            else:
                not_seen.remove(playlist.id)

        for playlist_id in not_seen:
            print(playlist_id)

        self.playlist_list.show_all()
        self.set_playlist_list_loading(False)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_playlist(*a, **k),
        before_fn=lambda self: self.set_playlist_view_loading(True),
    )
    def update_playlist_view(self, playlist):
        # Update the Playlist Info panel
        self.update_playlist_artwork(playlist.coverArt)
        self.playlist_indicator.set_markup('PLAYLIST')
        self.playlist_name.set_markup(f'<b>{playlist.name}</b>')
        if playlist.comment:
            self.playlist_comment.set_text(playlist.comment)
            self.playlist_comment.show()
        else:
            self.playlist_comment.hide()
        self.playlist_stats.set_markup(self.format_stats(playlist))

        # Update the song list model
        self.playlist_song_model.clear()
        for song in (playlist.entry or []):
            cache_icon = {
                SongCacheStatus.NOT_CACHED: '',
                SongCacheStatus.CACHED: 'folder-download-symbolic',
                SongCacheStatus.PERMANENTLY_CACHED: 'view-pin-symbolic',
                SongCacheStatus.DOWNLOADING: 'emblem-synchronizing-symbolic',
            }
            self.playlist_song_model.append([
                cache_icon[CacheManager.get_cached_status(song)],
                song.title,
                song.album,
                song.artist,
                util.format_song_duration(song.duration),
                song.id,
            ])
        self.set_playlist_view_loading(False)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_cover_art_filename(*a, **k),
        before_fn=lambda self: self.set_playlist_art_loading(True),
    )
    def update_playlist_artwork(self, cover_art_filename):
        self.playlist_artwork.set_from_file(cover_art_filename)
        self.set_playlist_art_loading(False)

    def create_playlist_label(self, playlist: PlaylistWithSongs):
        return self.make_label(f'<b>{playlist.name}</b>',
                               use_markup=True,
                               margin=12)

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
