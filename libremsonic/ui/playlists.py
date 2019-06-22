import gi
import sys

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk

from libremsonic.server.api_objects import Playlist
from libremsonic.state_manager import ApplicationState


class PlaylistsPanel(Gtk.Paned):
    """Defines the playlists panel."""

    def __init__(self):
        Gtk.FlowBox.__init__(
            self,
            orientation=Gtk.Orientation.HORIZONTAL,
        )

        # The playlist list on the left side
        # =====================================================================
        playlist_list_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        list_scroll_window = Gtk.ScrolledWindow(min_content_width=200)
        self.playlist_list = Gtk.ListBox()
        list_scroll_window.add(self.playlist_list)
        playlist_list_vbox.pack_start(list_scroll_window, True, True, 0)

        # Add playlist button
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        add_icon = Gio.ThemedIcon(name='list-add')
        image = Gtk.Image.new_from_gicon(add_icon, Gtk.IconSize.LARGE_TOOLBAR)
        box.add(image)
        box.add(Gtk.Label('New Playlist', margin=10))

        self.new_playlist = Gtk.Button(name='new-playlist-button')
        self.new_playlist.add(box)
        playlist_list_vbox.pack_start(self.new_playlist, False, False, 0)
        self.pack1(playlist_list_vbox, False, False)

        # The playlist view on the right side
        # =====================================================================
        self.playlist_view = Gtk.ListBox()
        self.pack2(self.playlist_view, True, False)

    def update(self, state: ApplicationState):
        playlists = state.cache_manager.get_playlists()

        for c in self.playlist_list.get_children():
            self.playlist_list.remove(c)

        for playlist in playlists.playlist:
            self.playlist_list.add(self.create_playlist_label(playlist))

        self.playlist_list.show_all()

    def create_playlist_label(self, playlist: Playlist):
        return Gtk.Label(
            f'<b>{playlist.name}</b>',
            halign=Gtk.Align.START,
            use_markup=True,
            margin=10,
        )
