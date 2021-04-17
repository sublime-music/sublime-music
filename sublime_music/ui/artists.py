from datetime import timedelta
from functools import partial
from random import randint
from typing import cast, List, Sequence

import bleach

from gi.repository import Gio, GLib, GObject, Gtk, Pango

from ..adapters import (
    AdapterManager,
    api_objects as API,
    CacheMissError,
    SongCacheStatus,
)
from ..config import AppConfiguration
from ..ui import util
from ..ui.common import AlbumWithSongs, IconButton, LoadError, SpinnerImage


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
            "song-clicked",
            lambda _, *args: self.emit("song-clicked", *args),
        )
        self.artist_detail_panel.connect(
            "refresh-window",
            lambda _, *args: self.emit("refresh-window", *args),
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

        self.refresh_button = IconButton(
            "view-refresh-symbolic", "Refresh list of artists"
        )
        self.refresh_button.connect("clicked", lambda *a: self.update(force=True))
        list_actions.pack_end(self.refresh_button)

        self.add(list_actions)

        self.error_container = Gtk.Box()
        self.add(self.error_container)

        self.loading_indicator = Gtk.ListBox()
        spinner_row = Gtk.ListBoxRow(activatable=False, selectable=False)
        spinner = Gtk.Spinner(name="artist-list-spinner", active=True)
        spinner_row.add(spinner)
        self.loading_indicator.add(spinner_row)
        self.pack_start(self.loading_indicator, False, False, 0)

        list_scroll_window = Gtk.ScrolledWindow(min_content_width=250)

        def create_artist_row(model: _ArtistModel) -> Gtk.ListBoxRow:
            label_text = [f"<b>{model.name}</b>"]

            if album_count := model.album_count:
                label_text.append(
                    "{} {}".format(album_count, util.pluralize("album", album_count))
                )

            row = Gtk.ListBoxRow(
                action_name="app.go-to-artist",
                action_target=GLib.Variant("s", model.artist_id),
            )
            row.add(
                Gtk.Label(
                    label=bleach.clean("\n".join(label_text)),
                    use_markup=True,
                    margin=12,
                    halign=Gtk.Align.START,
                    ellipsize=Pango.EllipsizeMode.END,
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
        is_partial: bool = False,
        **kwargs,
    ):
        if app_config:
            self._app_config = app_config
            self.refresh_button.set_sensitive(not app_config.offline_mode)

        for c in self.error_container.get_children():
            self.error_container.remove(c)
        if is_partial:
            load_error = LoadError(
                "Artist list",
                "load artists",
                has_data=len(artists) > 0,
                offline_mode=(
                    self._app_config.offline_mode if self._app_config else False
                ),
            )
            self.error_container.pack_start(load_error, True, True, 0)
            self.error_container.show_all()
        else:
            self.error_container.hide()

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


class ArtistDetailPanel(Gtk.Box):
    """Defines the artists list."""

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

    update_order_token = 0
    artist_details_expanded = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            name="artist-detail-panel",
            orientation=Gtk.Orientation.VERTICAL,
            **kwargs,
        )
        self.albums: Sequence[API.Album] = []
        self.artist_id = None

        # Artist info panel
        self.big_info_panel = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, name="artist-info-panel"
        )

        self.artist_artwork = SpinnerImage(
            loading=False,
            image_name="artist-album-artwork",
            spinner_name="artist-artwork-spinner",
            image_size=300,
        )
        self.big_info_panel.pack_start(self.artist_artwork, False, False, 0)

        # Action buttons, name, comment, number of songs, etc.
        artist_details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        artist_details_box.pack_start(Gtk.Box(), True, False, 0)

        self.artist_indicator = self.make_label(name="artist-indicator")
        artist_details_box.add(self.artist_indicator)

        self.artist_name = self.make_label(
            name="artist-name", ellipsize=Pango.EllipsizeMode.END
        )
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

        self.play_button = IconButton(
            "media-playback-start-symbolic", label="Play All", relief=True
        )
        self.play_button.connect("clicked", self.on_play_all_clicked)
        self.play_shuffle_buttons.pack_start(self.play_button, False, False, 0)

        self.shuffle_button = IconButton(
            "media-playlist-shuffle-symbolic", label="Shuffle All", relief=True
        )
        self.shuffle_button.connect("clicked", self.on_shuffle_all_button)
        self.play_shuffle_buttons.pack_start(self.shuffle_button, False, False, 5)
        artist_details_box.add(self.play_shuffle_buttons)

        self.big_info_panel.pack_start(artist_details_box, True, True, 0)

        # Action buttons
        action_buttons_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.artist_action_buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=10
        )

        self.download_all_button = IconButton(
            "folder-download-symbolic", "Download all songs by this artist"
        )
        self.download_all_button.connect("clicked", self.on_download_all_click)
        self.artist_action_buttons.add(self.download_all_button)

        self.refresh_button = IconButton("view-refresh-symbolic", "Refresh artist info")
        self.refresh_button.connect("clicked", self.on_view_refresh_click)
        self.artist_action_buttons.add(self.refresh_button)

        action_buttons_container.pack_start(
            self.artist_action_buttons, False, False, 10
        )

        action_buttons_container.pack_start(Gtk.Box(), True, True, 0)

        expand_button_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.expand_collapse_button = IconButton(
            "pan-up-symbolic", "Expand playlist details"
        )
        self.expand_collapse_button.connect("clicked", self.on_expand_collapse_click)
        expand_button_container.pack_end(self.expand_collapse_button, False, False, 0)
        action_buttons_container.add(expand_button_container)

        self.big_info_panel.pack_start(action_buttons_container, False, False, 5)

        self.pack_start(self.big_info_panel, False, True, 0)

        self.error_container = Gtk.Box()
        self.add(self.error_container)

        self.album_list_scrolledwindow = Gtk.ScrolledWindow()
        self.albums_list = AlbumsListWithSongs()
        self.albums_list.connect(
            "song-clicked",
            lambda _, *args: self.emit("song-clicked", *args),
        )
        self.album_list_scrolledwindow.add(self.albums_list)
        self.pack_start(self.album_list_scrolledwindow, True, True, 0)

    def update(self, app_config: AppConfiguration):
        self.artist_id = app_config.state.selected_artist_id
        self.offline_mode = app_config.offline_mode
        if app_config.state.selected_artist_id is None:
            self.big_info_panel.hide()
            self.album_list_scrolledwindow.hide()
            self.play_shuffle_buttons.hide()
        else:
            self.update_order_token += 1
            self.album_list_scrolledwindow.show()
            self.update_artist_view(
                app_config.state.selected_artist_id,
                app_config=app_config,
                order_token=self.update_order_token,
            )
            self.refresh_button.set_sensitive(not self.offline_mode)
            self.download_all_button.set_sensitive(not self.offline_mode)

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
        is_partial: bool = False,
    ):
        if order_token != self.update_order_token:
            return

        self.big_info_panel.show_all()

        if app_config:
            self.artist_details_expanded = app_config.state.artist_details_expanded

        up_down = "up" if self.artist_details_expanded else "down"
        self.expand_collapse_button.set_icon(f"pan-{up_down}-symbolic")
        self.expand_collapse_button.set_tooltip_text(
            "Collapse" if self.artist_details_expanded else "Expand"
        )

        self.artist_name.set_markup(bleach.clean(f"<b>{artist.name}</b>"))
        self.artist_name.set_tooltip_text(artist.name)

        if self.artist_details_expanded:
            self.artist_artwork.get_style_context().remove_class("collapsed")
            self.artist_name.get_style_context().remove_class("collapsed")
            self.artist_indicator.set_text("ARTIST")
            self.artist_stats.set_markup(self.format_stats(artist))

            if artist.biography:
                self.artist_bio.set_markup(bleach.clean(artist.biography))
                self.artist_bio.show()
            else:
                self.artist_bio.hide()

            if len(artist.similar_artists or []) > 0:
                self.similar_artists_label.set_markup("<b>Similar Artists:</b> ")
                for c in self.similar_artists_button_box.get_children():
                    self.similar_artists_button_box.remove(c)

                for similar_artist in (artist.similar_artists or [])[:5]:
                    self.similar_artists_button_box.add(
                        Gtk.LinkButton(
                            label=similar_artist.name,
                            name="similar-artist-button",
                            action_name="app.go-to-artist",
                            action_target=GLib.Variant("s", similar_artist.id),
                        )
                    )
                self.similar_artists_scrolledwindow.show_all()
            else:
                self.similar_artists_scrolledwindow.hide()
        else:
            self.artist_artwork.get_style_context().add_class("collapsed")
            self.artist_name.get_style_context().add_class("collapsed")
            self.artist_indicator.hide()
            self.artist_stats.hide()
            self.artist_bio.hide()
            self.similar_artists_scrolledwindow.hide()

        self.play_shuffle_buttons.show_all()

        self.update_artist_artwork(
            artist.artist_image_url,
            force=force,
            order_token=order_token,
        )

        for c in self.error_container.get_children():
            self.error_container.remove(c)
        if is_partial:
            has_data = len(artist.albums or []) > 0
            load_error = LoadError(
                "Artist data",
                "load artist details",
                has_data=has_data,
                offline_mode=self.offline_mode,
            )
            self.error_container.pack_start(load_error, True, True, 0)
            self.error_container.show_all()
            if not has_data:
                self.album_list_scrolledwindow.hide()
        else:
            self.error_container.hide()
            self.album_list_scrolledwindow.show()

        self.albums = artist.albums or []

        # (Dis|En)able the "Play All" and "Shuffle All" buttons. If in offline mode, it
        # depends on whether or not there are any cached songs.
        if self.offline_mode:
            has_cached_song = False
            playable_statuses = (
                SongCacheStatus.CACHED,
                SongCacheStatus.PERMANENTLY_CACHED,
            )

            for album in self.albums:
                if album.id:
                    try:
                        songs = AdapterManager.get_album(album.id).result().songs or []
                    except CacheMissError as e:
                        if e.partial_data:
                            songs = cast(API.Album, e.partial_data).songs or []
                        else:
                            songs = []
                    statuses = AdapterManager.get_cached_statuses([s.id for s in songs])
                    if any(s in playable_statuses for s in statuses):
                        has_cached_song = True
                        break

            self.play_button.set_sensitive(has_cached_song)
            self.shuffle_button.set_sensitive(has_cached_song)
        else:
            self.play_button.set_sensitive(not self.offline_mode)
            self.shuffle_button.set_sensitive(not self.offline_mode)

        self.albums_list.update(artist, app_config, force=force)

    @util.async_callback(
        partial(AdapterManager.get_cover_art_uri, scheme="file"),
        before_download=lambda self: self.artist_artwork.set_loading(True),
        on_failure=lambda self, e: self.artist_artwork.set_loading(False),
    )
    def update_artist_artwork(
        self,
        cover_art_filename: str,
        app_config: AppConfiguration,
        force: bool = False,
        order_token: int = None,
        is_partial: bool = False,
    ):
        if order_token != self.update_order_token:
            return
        self.artist_artwork.set_from_file(cover_art_filename)
        self.artist_artwork.set_loading(False)

        if self.artist_details_expanded:
            self.artist_artwork.set_image_size(300)
        else:
            self.artist_artwork.set_image_size(70)

    # Event Handlers
    # =========================================================================
    def on_view_refresh_click(self, *args):
        self.update_artist_view(
            self.artist_id,
            force=True,
            order_token=self.update_order_token,
        )

    def on_download_all_click(self, _):
        AdapterManager.batch_download_songs(
            self.get_artist_song_ids(),
            before_download=lambda _: self.update_artist_view(
                self.artist_id,
                order_token=self.update_order_token,
            ),
            on_song_download_complete=lambda _: self.update_artist_view(
                self.artist_id,
                order_token=self.update_order_token,
            ),
        )

    def on_play_all_clicked(self, _):
        songs = self.get_artist_song_ids()
        self.emit(
            "song-clicked",
            0,
            songs,
            {"force_shuffle_state": False},
        )

    def on_shuffle_all_button(self, _):
        songs = self.get_artist_song_ids()
        self.emit(
            "song-clicked",
            randint(0, len(songs) - 1),
            songs,
            {"force_shuffle_state": True},
        )

    def on_expand_collapse_click(self, _):
        self.emit(
            "refresh-window",
            {"artist_details_expanded": not self.artist_details_expanded},
            False,
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

    def make_label(self, text: str = None, name: str = None, **params) -> Gtk.Label:
        return Gtk.Label(
            label=text, name=name, halign=Gtk.Align.START, xalign=0, **params
        )

    def format_stats(self, artist: API.Artist) -> str:
        album_count = artist.album_count or len(artist.albums or [])
        song_count, duration = 0, timedelta(0)
        for album in artist.albums or []:
            song_count += album.song_count or 0
            duration += album.duration or timedelta(0)

        return util.dot_join(
            "{} {}".format(album_count, util.pluralize("album", album_count)),
            "{} {}".format(song_count, util.pluralize("song", song_count)),
            util.format_sequence_duration(duration),
        )

    def get_artist_song_ids(self) -> List[str]:
        try:
            artist = AdapterManager.get_artist(self.artist_id).result()
        except CacheMissError as c:
            artist = cast(API.Artist, c.partial_data)

        if not artist:
            return []

        songs = []
        for album in artist.albums or []:
            assert album.id
            try:
                album_with_songs = AdapterManager.get_album(album.id).result()
            except CacheMissError as c:
                album_with_songs = cast(API.Album, c.partial_data)
            if not album_with_songs:
                continue
            for song in album_with_songs.songs or []:
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

    def update(
        self, artist: API.Artist, app_config: AppConfiguration, force: bool = False
    ):
        def remove_all():
            for c in self.box.get_children():
                self.box.remove(c)

        if artist is None:
            remove_all()
            self.spinner.hide()
            return

        new_albums = sorted(
            artist.albums or [], key=lambda a: (a.year or float("inf"), a.name)
        )

        if self.albums == new_albums:
            # Just go through all of the colidren and update them.
            for c in self.box.get_children():
                c.update(app_config=app_config, force=force)

            self.spinner.hide()
            return

        self.albums = new_albums

        remove_all()

        for album in self.albums:
            album_with_songs = AlbumWithSongs(album, show_artist_name=False)
            album_with_songs.connect(
                "song-clicked",
                lambda _, *args: self.emit("song-clicked", *args),
            )
            album_with_songs.connect("song-selected", self.on_song_selected)
            album_with_songs.show_all()
            self.box.add(album_with_songs)

        # Update everything (no force to ensure that if we are online, then everything
        # is clickable)
        for c in self.box.get_children():
            c.update(app_config=app_config)

        self.spinner.hide()

    def on_song_selected(self, album_component: AlbumWithSongs):
        for child in self.box.get_children():
            if album_component != child:
                child.deselect_all()
