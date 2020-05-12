import math
from random import randint
from typing import Any, List, Sequence

from gi.repository import Gio, GLib, GObject, Gtk, Pango

from sublime.adapters import AdapterManager, api_objects as API
from sublime.cache_manager import CacheManager
from sublime.config import AppConfiguration
from sublime.ui import util
from sublime.ui.common import AlbumWithSongs, IconButton, SpinnerImage


class ArtistsPanel(Gtk.Paned):
    """Defines the arist panel."""

    __gsignals__ = {
        "song-clicked": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        "refresh-window": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    def __init__(self, *args, **kwargs):
        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)

        self.artist_list = ArtistList()
        self.pack1(self.artist_list, False, False)

        self.artist_detail_panel = ArtistDetailPanel()
        self.artist_detail_panel.connect(
            "song-clicked", lambda _, *args: self.emit("song-clicked", *args),
        )
        self.pack2(self.artist_detail_panel, True, False)

    def update(self, app_config: AppConfiguration, force: bool = False):
        self.artist_list.update(app_config=app_config)
        self.artist_detail_panel.update(app_config=app_config)


class _ArtistModel(GObject.GObject):
    artist_id = GObject.Property(type=str)
    name = GObject.Property(type=str)
    album_count = GObject.Property(type=int)

    def __init__(self, artist: API.Artist):
        GObject.GObject.__init__(self)
        self.artist_id = artist.id
        self.name = artist.name
        self.album_count = artist.album_count or 0


class ArtistList(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        list_actions = Gtk.ActionBar()

        refresh = IconButton("view-refresh-symbolic", "Refresh list of artists")
        refresh.connect("clicked", lambda *a: self.update(force=True))
        list_actions.pack_end(refresh)

        self.add(list_actions)

        self.loading_indicator = Gtk.ListBox()
        spinner_row = Gtk.ListBoxRow(activatable=False, selectable=False)
        spinner = Gtk.Spinner(name="artist-list-spinner", active=True)
        spinner_row.add(spinner)
        self.loading_indicator.add(spinner_row)
        self.pack_start(self.loading_indicator, False, False, 0)

        list_scroll_window = Gtk.ScrolledWindow(min_content_width=250)

        def create_artist_row(model: _ArtistModel) -> Gtk.ListBoxRow:
            label_text = [f"<b>{util.esc(model.name)}</b>"]

            album_count = model.album_count
            if album_count:
                label_text.append(
                    "{} {}".format(album_count, util.pluralize("album", album_count))
                )

            row = Gtk.ListBoxRow(
                action_name="app.go-to-artist",
                action_target=GLib.Variant("s", model.artist_id),
            )
            row.add(
                Gtk.Label(
                    label="\n".join(label_text),
                    use_markup=True,
                    margin=12,
                    halign=Gtk.Align.START,
                    ellipsize=Pango.EllipsizeMode.END,
                    max_width_chars=30,
                )
            )
            row.show_all()
            return row

        self.artists_store = Gio.ListStore()
        self.list = Gtk.ListBox(name="artist-list")
        self.list.bind_model(self.artists_store, create_artist_row)
        list_scroll_window.add(self.list)

        self.pack_start(list_scroll_window, True, True, 0)

    _app_config = None

    @util.async_callback(
        AdapterManager.get_artists,
        before_download=lambda self: self.loading_indicator.show_all(),
        on_failure=lambda self, e: self.loading_indicator.hide(),
    )
    def update(
        self,
        artists: Sequence[API.Artist],
        app_config: AppConfiguration = None,
        **kwargs,
    ):
        if app_config:
            self._app_config = app_config

        new_store = []
        selected_idx = None
        for i, artist in enumerate(artists):
            if (
                self._app_config
                and self._app_config.state
                and self._app_config.state.selected_artist_id == artist.id
            ):
                selected_idx = i
            new_store.append(_ArtistModel(artist))

        util.diff_model_store(self.artists_store, new_store)

        # Preserve selection
        if selected_idx is not None:
            row = self.list.get_row_at_index(selected_idx)
            self.list.select_row(row)

        self.loading_indicator.hide()


class ArtistDetailPanel(Gtk.ScrolledWindow):
    """Defines the artists list."""

    __gsignals__ = {
        "song-clicked": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
    }

    update_order_token = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, name="artist-detail-panel", **kwargs)
        self.albums: Sequence[API.Album] = []
        self.artist_id = None

        artist_info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Artist info panel
        self.big_info_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.artist_artwork = SpinnerImage(
            loading=False,
            image_name="artist-album-artwork",
            spinner_name="artist-artwork-spinner",
            image_size=300,
        )
        self.big_info_panel.pack_start(self.artist_artwork, False, False, 0)

        # Action buttons, name, comment, number of songs, etc.
        artist_details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Action buttons (note we are packing end here, so we have to put them
        # in right-to-left).
        self.artist_action_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        view_refresh_button = IconButton("view-refresh-symbolic", "Refresh artist info")
        view_refresh_button.connect("clicked", self.on_view_refresh_click)
        self.artist_action_buttons.pack_end(view_refresh_button, False, False, 5)

        download_all_btn = IconButton(
            "folder-download-symbolic", "Download all songs by this artist"
        )
        download_all_btn.connect("clicked", self.on_download_all_click)
        self.artist_action_buttons.pack_end(download_all_btn, False, False, 5)

        artist_details_box.pack_start(self.artist_action_buttons, False, False, 5)

        artist_details_box.pack_start(Gtk.Box(), True, False, 0)

        self.artist_indicator = self.make_label(name="artist-indicator")
        artist_details_box.add(self.artist_indicator)

        self.artist_name = self.make_label(name="artist-name")
        artist_details_box.add(self.artist_name)

        self.artist_bio = self.make_label(
            name="artist-bio", justify=Gtk.Justification.LEFT
        )
        self.artist_bio.set_line_wrap(True)
        artist_details_box.add(self.artist_bio)

        self.similar_artists_scrolledwindow = Gtk.ScrolledWindow()
        similar_artists_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.similar_artists_label = self.make_label(name="similar-artists")
        similar_artists_box.add(self.similar_artists_label)

        self.similar_artists_button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL
        )
        similar_artists_box.add(self.similar_artists_button_box)
        self.similar_artists_scrolledwindow.add(similar_artists_box)

        artist_details_box.add(self.similar_artists_scrolledwindow)

        self.artist_stats = self.make_label(name="artist-stats")
        artist_details_box.add(self.artist_stats)

        self.play_shuffle_buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            name="playlist-play-shuffle-buttons",
        )

        play_button = IconButton(
            "media-playback-start-symbolic", label="Play All", relief=True,
        )
        play_button.connect("clicked", self.on_play_all_clicked)
        self.play_shuffle_buttons.pack_start(play_button, False, False, 0)

        shuffle_button = IconButton(
            "media-playlist-shuffle-symbolic", label="Shuffle All", relief=True,
        )
        shuffle_button.connect("clicked", self.on_shuffle_all_button)
        self.play_shuffle_buttons.pack_start(shuffle_button, False, False, 5)
        artist_details_box.add(self.play_shuffle_buttons)

        self.big_info_panel.pack_start(artist_details_box, True, True, 10)

        artist_info_box.pack_start(self.big_info_panel, False, True, 0)

        self.albums_list = AlbumsListWithSongs()
        self.albums_list.connect(
            "song-clicked", lambda _, *args: self.emit("song-clicked", *args),
        )
        artist_info_box.pack_start(self.albums_list, True, True, 0)

        self.add(artist_info_box)

    def update(self, app_config: AppConfiguration):
        self.artist_id = app_config.state.selected_artist_id
        if app_config.state.selected_artist_id is None:
            self.artist_action_buttons.hide()
            self.artist_indicator.set_text("")
            self.artist_name.set_markup("")
            self.artist_stats.set_markup("")

            self.artist_bio.set_markup("")
            self.similar_artists_scrolledwindow.hide()
            self.play_shuffle_buttons.hide()

            self.artist_artwork.set_from_file(None)

            self.albums = []
            self.albums_list.update(None)
        else:
            self.update_order_token += 1
            self.artist_action_buttons.show()
            self.update_artist_view(
                app_config.state.selected_artist_id,
                app_config=app_config,
                order_token=self.update_order_token,
            )

    @util.async_callback(
        AdapterManager.get_artist,
        before_download=lambda self: self.set_all_loading(True),
        on_failure=lambda self, e: self.set_all_loading(False),
    )
    def update_artist_view(
        self,
        artist: API.Artist,
        app_config: AppConfiguration,
        force: bool = False,
        order_token: int = None,
    ):
        if order_token != self.update_order_token:
            return

        self.artist_indicator.set_text("ARTIST")
        self.artist_name.set_markup(util.esc(f"<b>{artist.name}</b>"))
        self.artist_stats.set_markup(self.format_stats(artist))

        self.artist_bio.set_markup(util.esc(artist.biography))

        if len(artist.similar_artists or []) > 0:
            self.similar_artists_label.set_markup("<b>Similar Artists:</b> ")
            for c in self.similar_artists_button_box.get_children():
                self.similar_artists_button_box.remove(c)

            for artist in (artist.similar_artists or [])[:5]:
                self.similar_artists_button_box.add(
                    Gtk.LinkButton(
                        label=artist.name,
                        name="similar-artist-button",
                        action_name="app.go-to-artist",
                        action_target=GLib.Variant("s", artist.id),
                    )
                )
            self.similar_artists_scrolledwindow.show_all()
        else:
            self.similar_artists_scrolledwindow.hide()

        self.play_shuffle_buttons.show_all()

        self.update_artist_artwork(
            artist.artist_image_url, force=force, order_token=order_token,
        )

        self.albums = artist.albums or []
        self.albums_list.update(artist)

    @util.async_callback(
        AdapterManager.get_cover_art_filename,
        before_download=lambda self: self.artist_artwork.set_loading(True),
        on_failure=lambda self, e: self.artist_artwork.set_loading(False),
    )
    def update_artist_artwork(
        self,
        cover_art_filename: str,
        app_config: AppConfiguration,
        force: bool = False,
        order_token: int = None,
    ):
        if order_token != self.update_order_token:
            return
        self.artist_artwork.set_from_file(cover_art_filename)
        self.artist_artwork.set_loading(False)

    # Event Handlers
    # =========================================================================
    def on_view_refresh_click(self, *args):
        self.update_artist_view(
            self.artist_id, force=True, order_token=self.update_order_token,
        )

    def on_download_all_click(self, btn: Any):
        AdapterManager.batch_download_songs(
            self.get_artist_song_ids(),
            before_download=lambda _: self.update_artist_view(
                self.artist_id, order_token=self.update_order_token,
            ),
            on_song_download_complete=lambda _: self.update_artist_view(
                self.artist_id, order_token=self.update_order_token,
            ),
        )

    def on_play_all_clicked(self, btn: Any):
        songs = self.get_artist_song_ids()
        self.emit(
            "song-clicked", 0, songs, {"force_shuffle_state": False},
        )

    def on_shuffle_all_button(self, btn: Any):
        songs = self.get_artist_song_ids()
        self.emit(
            "song-clicked",
            randint(0, len(songs) - 1),
            songs,
            {"force_shuffle_state": True},
        )

    # Helper Methods
    # =========================================================================
    def set_all_loading(self, loading_state: bool):
        if loading_state:
            self.albums_list.spinner.start()
            self.albums_list.spinner.show()
            self.artist_artwork.set_loading(True)
        else:
            self.albums_list.spinner.hide()
            self.artist_artwork.set_loading(False)

    def make_label(self, text: str = None, name: str = None, **params,) -> Gtk.Label:
        return Gtk.Label(
            label=text, name=name, halign=Gtk.Align.START, xalign=0, **params,
        )

    def format_stats(self, artist: API.Artist) -> str:
        album_count = artist.album_count or 0
        song_count = sum(a.song_count for a in artist.albums or []) or 0
        duration = math.floor(
            sum(
                (a.duration.total_seconds() if a.duration else 0)
                for a in artist.albums or []
            )
        )
        return util.dot_join(
            "{} {}".format(album_count, util.pluralize("album", album_count)),
            "{} {}".format(song_count, util.pluralize("song", song_count)),
            util.format_sequence_duration(duration),
        )

    def get_artist_song_ids(self) -> List[str]:
        songs = []
        for album in AdapterManager.get_artist(self.artist_id).result().albums or []:
            album_songs = AdapterManager.get_album(album.id).result()
            for song in album_songs.songs or []:
                songs.append(song.id)

        return songs


class AlbumsListWithSongs(Gtk.Overlay):
    __gsignals__ = {
        "song-clicked": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
    }

    def __init__(self):
        Gtk.Overlay.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(self.box)

        self.spinner = Gtk.Spinner(
            name="albumslist-with-songs-spinner",
            active=False,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        self.add_overlay(self.spinner)

        self.albums = []

    def update(self, artist: API.Artist):
        def remove_all():
            for c in self.box.get_children():
                self.box.remove(c)

        if artist is None:
            remove_all()
            self.spinner.hide()
            return

        new_albums = list(artist.albums or [])

        if self.albums == new_albums:
            # Just go through all of the colidren and update them.
            for c in self.box.get_children():
                c.update()

            self.spinner.hide()
            return

        self.albums = new_albums

        remove_all()

        for album in self.albums:
            album_with_songs = AlbumWithSongs(album, show_artist_name=False)
            album_with_songs.connect(
                "song-clicked", lambda _, *args: self.emit("song-clicked", *args),
            )
            album_with_songs.connect("song-selected", self.on_song_selected)
            album_with_songs.show_all()
            self.box.add(album_with_songs)

        self.spinner.stop()
        self.spinner.hide()

    def on_song_selected(self, album_component: AlbumWithSongs):
        for child in self.box.get_children():
            if album_component != child:
                child.deselect_all()
