import math
from functools import lru_cache, partial
from random import randint
from typing import Any, cast, Dict, List, Tuple

from fuzzywuzzy import fuzz
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from ..adapters import AdapterManager, api_objects as API
from ..config import AppConfiguration
from ..ui import util
from ..ui.common import (
    IconButton,
    LoadError,
    SongListColumn,
    SpinnerImage,
)


class EditPlaylistDialog(Gtk.Dialog):
    def __init__(self, parent: Any, playlist: API.Playlist):
        Gtk.Dialog.__init__(self, transient_for=parent, flags=Gtk.DialogFlags.MODAL)

        # HEADER
        self.header = Gtk.HeaderBar()
        self._set_title(playlist.name)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda _: self.close())
        self.header.pack_start(cancel_button)

        self.edit_button = Gtk.Button(label="Edit")
        self.edit_button.get_style_context().add_class("suggested-action")
        self.edit_button.connect(
            "clicked", lambda *a: self.response(Gtk.ResponseType.APPLY)
        )
        self.header.pack_end(self.edit_button)

        self.set_titlebar(self.header)

        content_area = self.get_content_area()
        content_grid = Gtk.Grid(column_spacing=10, row_spacing=10, margin=10)

        make_label = lambda label_text: Gtk.Label(label_text, halign=Gtk.Align.END)

        content_grid.attach(make_label("Playlist Name"), 0, 0, 1, 1)
        self.name_entry = Gtk.Entry(text=playlist.name, hexpand=True)
        self.name_entry.connect("changed", self._on_name_change)
        content_grid.attach(self.name_entry, 1, 0, 1, 1)

        content_grid.attach(make_label("Comment"), 0, 1, 1, 1)
        self.comment_entry = Gtk.Entry(text=playlist.comment, hexpand=True)
        content_grid.attach(self.comment_entry, 1, 1, 1, 1)

        content_grid.attach(make_label("Public"), 0, 2, 1, 1)
        self.public_switch = Gtk.Switch(active=playlist.public, halign=Gtk.Align.START)
        content_grid.attach(self.public_switch, 1, 2, 1, 1)

        delete_button = Gtk.Button(label="Delete")
        delete_button.connect("clicked", lambda *a: self.response(Gtk.ResponseType.NO))
        content_grid.attach(delete_button, 0, 3, 1, 2)

        content_area.add(content_grid)
        self.show_all()

    def _on_name_change(self, entry: Gtk.Entry):
        text = entry.get_text()
        if len(text) > 0:
            self._set_title(text)
        self.edit_button.set_sensitive(len(text) > 0)

    def _set_title(self, playlist_name: str):
        self.header.props.title = f"Edit {playlist_name}"

    def get_data(self) -> Dict[str, Any]:
        return {
            "name": self.name_entry.get_text(),
            "comment": self.comment_entry.get_text(),
            "public": self.public_switch.get_active(),
        }


class PlaylistsPanel(Gtk.Paned):
    """Defines the playlists panel."""

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

        self.playlist_list = PlaylistList()
        self.pack1(self.playlist_list, False, False)

        self.playlist_detail_panel = PlaylistDetailPanel()
        self.playlist_detail_panel.connect(
            "song-clicked",
            lambda _, *args: self.emit("song-clicked", *args),
        )
        self.playlist_detail_panel.connect(
            "refresh-window",
            lambda _, *args: self.emit("refresh-window", *args),
        )
        self.pack2(self.playlist_detail_panel, True, False)

    def update(self, app_config: AppConfiguration = None, force: bool = False):
        self.playlist_list.update(app_config=app_config, force=force)
        self.playlist_detail_panel.update(app_config=app_config, force=force)


class PlaylistList(Gtk.Box):
    __gsignals__ = {
        "refresh-window": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    offline_mode = False

    class PlaylistModel(GObject.GObject):
        playlist_id = GObject.Property(type=str)
        name = GObject.Property(type=str)

        def __init__(self, playlist_id: str, name: str):
            GObject.GObject.__init__(self)
            self.playlist_id = playlist_id
            self.name = name

    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        playlist_list_actions = Gtk.ActionBar()

        self.new_playlist_button = IconButton("list-add-symbolic", label="New Playlist")
        self.new_playlist_button.connect("clicked", self.on_new_playlist_clicked)
        playlist_list_actions.pack_start(self.new_playlist_button)

        self.list_refresh_button = IconButton(
            "view-refresh-symbolic", "Refresh list of playlists"
        )
        self.list_refresh_button.connect("clicked", self.on_list_refresh_click)
        playlist_list_actions.pack_end(self.list_refresh_button)

        self.add(playlist_list_actions)

        self.error_container = Gtk.Box()
        self.add(self.error_container)

        loading_new_playlist = Gtk.ListBox()

        self.loading_indicator = Gtk.ListBoxRow(activatable=False, selectable=False)
        loading_spinner = Gtk.Spinner(name="playlist-list-spinner", active=True)
        self.loading_indicator.add(loading_spinner)
        loading_new_playlist.add(self.loading_indicator)

        self.new_playlist_row = Gtk.ListBoxRow(activatable=False, selectable=False)
        new_playlist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=False)

        self.new_playlist_entry = Gtk.Entry(name="playlist-list-new-playlist-entry")
        self.new_playlist_entry.connect("activate", self.new_entry_activate)
        new_playlist_box.add(self.new_playlist_entry)

        new_playlist_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        confirm_button = IconButton(
            "object-select-symbolic",
            "Create playlist",
            name="playlist-list-new-playlist-confirm",
            relief=True,
        )
        confirm_button.connect("clicked", self.confirm_button_clicked)
        new_playlist_actions.pack_end(confirm_button, False, True, 0)

        self.cancel_button = IconButton(
            "process-stop-symbolic",
            "Cancel create playlist",
            name="playlist-list-new-playlist-cancel",
            relief=True,
        )
        self.cancel_button.connect("clicked", self.cancel_button_clicked)
        new_playlist_actions.pack_end(self.cancel_button, False, True, 0)

        new_playlist_box.add(new_playlist_actions)
        self.new_playlist_row.add(new_playlist_box)

        loading_new_playlist.add(self.new_playlist_row)
        self.add(loading_new_playlist)

        list_scroll_window = Gtk.ScrolledWindow(min_content_width=220)

        def create_playlist_row(model: PlaylistList.PlaylistModel) -> Gtk.ListBoxRow:
            row = Gtk.ListBoxRow(
                action_name="app.go-to-playlist",
                action_target=GLib.Variant("s", model.playlist_id),
            )
            row.add(
                Gtk.Label(
                    label=f"<b>{model.name}</b>",
                    use_markup=True,
                    margin=10,
                    halign=Gtk.Align.START,
                    ellipsize=Pango.EllipsizeMode.END,
                )
            )
            row.show_all()
            return row

        self.playlists_store = Gio.ListStore()
        self.list = Gtk.ListBox(name="playlist-list-listbox")
        self.list.bind_model(self.playlists_store, create_playlist_row)
        list_scroll_window.add(self.list)
        self.pack_start(list_scroll_window, True, True, 0)

    def update(self, app_config: AppConfiguration = None, force: bool = False):
        if app_config:
            self.offline_mode = app_config.offline_mode
            self.new_playlist_button.set_sensitive(not app_config.offline_mode)
            self.list_refresh_button.set_sensitive(not app_config.offline_mode)
        self.new_playlist_row.hide()
        self.update_list(app_config=app_config, force=force)

    @util.async_callback(
        AdapterManager.get_playlists,
        before_download=lambda self: self.loading_indicator.show_all(),
        on_failure=lambda self, e: self.loading_indicator.hide(),
    )
    def update_list(
        self,
        playlists: List[API.Playlist],
        app_config: AppConfiguration = None,
        force: bool = False,
        order_token: int = None,
        is_partial: bool = False,
    ):
        for c in self.error_container.get_children():
            self.error_container.remove(c)
        if is_partial:
            load_error = LoadError(
                "Playlist list",
                "load playlists",
                has_data=len(playlists) > 0,
                offline_mode=self.offline_mode,
            )
            self.error_container.pack_start(load_error, True, True, 0)
            self.error_container.show_all()
        else:
            self.error_container.hide()

        new_store = []
        selected_idx = None
        for i, playlist in enumerate(playlists or []):
            if (
                app_config
                and app_config.state
                and app_config.state.selected_playlist_id == playlist.id
            ):
                selected_idx = i

            new_store.append(PlaylistList.PlaylistModel(playlist.id, playlist.name))

        util.diff_model_store(self.playlists_store, new_store)

        # Preserve selection
        if selected_idx is not None:
            row = self.list.get_row_at_index(selected_idx)
            self.list.select_row(row)

        self.loading_indicator.hide()

    # Event Handlers
    # =========================================================================
    def on_new_playlist_clicked(self, _):
        self.new_playlist_entry.set_text("Untitled Playlist")
        self.new_playlist_entry.grab_focus()
        self.new_playlist_row.show()

    def on_list_refresh_click(self, _):
        self.update(force=True)

    def new_entry_activate(self, entry: Gtk.Entry):
        self.create_playlist(entry.get_text())

    def cancel_button_clicked(self, _):
        self.new_playlist_row.hide()

    def confirm_button_clicked(self, _):
        self.create_playlist(self.new_playlist_entry.get_text())

    def create_playlist(self, playlist_name: str):
        def on_playlist_created(_):
            self.update(force=True)

        self.loading_indicator.show()
        playlist_ceate_future = AdapterManager.create_playlist(name=playlist_name)
        playlist_ceate_future.add_done_callback(
            lambda f: GLib.idle_add(on_playlist_created, f)
        )


class PlaylistDetailPanel(Gtk.Overlay):
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

    playlist_id = None
    playlist_details_expanded = False
    offline_mode = False

    editing_playlist_song_list: bool = False
    reordering_playlist_song_list: bool = False

    def __init__(self):
        Gtk.Overlay.__init__(self, name="playlist-view-overlay")
        self.playlist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        playlist_info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.playlist_artwork = SpinnerImage(
            image_name="playlist-album-artwork",
            spinner_name="playlist-artwork-spinner",
            image_size=200,
        )
        playlist_info_box.add(self.playlist_artwork)

        # Name, comment, number of songs, etc.
        playlist_details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        playlist_details_box.pack_start(Gtk.Box(), True, False, 0)

        self.playlist_indicator = self.make_label(name="playlist-indicator")
        playlist_details_box.add(self.playlist_indicator)

        self.playlist_name = self.make_label(name="playlist-name")
        playlist_details_box.add(self.playlist_name)

        self.playlist_comment = self.make_label(name="playlist-comment")
        playlist_details_box.add(self.playlist_comment)

        self.playlist_stats = self.make_label(name="playlist-stats")
        playlist_details_box.add(self.playlist_stats)

        self.play_shuffle_buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            name="playlist-play-shuffle-buttons",
        )

        self.play_all_button = IconButton(
            "media-playback-start-symbolic",
            label="Play All",
            relief=True,
        )
        self.play_all_button.connect("clicked", self.on_play_all_clicked)
        self.play_shuffle_buttons.pack_start(self.play_all_button, False, False, 0)

        self.shuffle_all_button = IconButton(
            "media-playlist-shuffle-symbolic",
            label="Shuffle All",
            relief=True,
        )
        self.shuffle_all_button.connect("clicked", self.on_shuffle_all_button)
        self.play_shuffle_buttons.pack_start(self.shuffle_all_button, False, False, 5)

        playlist_details_box.add(self.play_shuffle_buttons)

        playlist_info_box.pack_start(playlist_details_box, True, True, 0)

        # Action buttons & expand/collapse button
        action_buttons_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.playlist_action_buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=10
        )

        self.download_all_button = IconButton(
            "folder-download-symbolic", "Download all songs in the playlist"
        )
        self.download_all_button.connect(
            "clicked", self.on_playlist_list_download_all_button_click
        )
        self.playlist_action_buttons.add(self.download_all_button)

        self.playlist_edit_button = IconButton("document-edit-symbolic", "Edit paylist")
        self.playlist_edit_button.connect("clicked", self.on_playlist_edit_button_click)
        self.playlist_action_buttons.add(self.playlist_edit_button)

        self.view_refresh_button = IconButton(
            "view-refresh-symbolic", "Refresh playlist info"
        )
        self.view_refresh_button.connect("clicked", self.on_view_refresh_click)
        self.playlist_action_buttons.add(self.view_refresh_button)

        action_buttons_container.pack_start(
            self.playlist_action_buttons, False, False, 10
        )

        action_buttons_container.pack_start(Gtk.Box(), True, True, 0)

        expand_button_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.expand_collapse_button = IconButton(
            "pan-up-symbolic", "Expand playlist details"
        )
        self.expand_collapse_button.connect("clicked", self.on_expand_collapse_click)
        expand_button_container.pack_end(self.expand_collapse_button, False, False, 0)
        action_buttons_container.add(expand_button_container)

        playlist_info_box.pack_end(action_buttons_container, False, False, 5)

        self.playlist_box.add(playlist_info_box)

        self.error_container = Gtk.Box()
        self.playlist_box.add(self.error_container)

        # Playlist songs list
        self.playlist_song_scroll_window = Gtk.ScrolledWindow()

        self.playlist_song_store = Gtk.ListStore(
            bool,  # clickable
            str,  # cache status
            str,  # title
            str,  # album
            str,  # artist
            str,  # duration
            str,  # song ID
        )

        @lru_cache(maxsize=1024)
        def row_score(key: str, row_items: Tuple[str]) -> int:
            return fuzz.partial_ratio(key, " ".join(row_items).lower())

        def playlist_song_list_search_fn(
            store: Gtk.ListStore,
            col: int,
            key: str,
            treeiter: Gtk.TreeIter,
            data: Any = None,
        ) -> bool:
            threshold = math.ceil(math.ceil(len(key) * 0.8) / len(key) * 100)
            return row_score(key.lower(), tuple(store[treeiter][2:5])) < threshold

        self.playlist_songs = Gtk.TreeView(
            model=self.playlist_song_store,
            reorderable=True,
            margin_top=15,
            enable_search=True,
        )
        self.playlist_songs.set_search_equal_func(playlist_song_list_search_fn)
        selection = self.playlist_songs.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.set_select_function(lambda _, model, path, current: model[path[0]][0])

        # Song status column.
        renderer = Gtk.CellRendererPixbuf()
        renderer.set_fixed_size(30, 35)
        column = Gtk.TreeViewColumn("", renderer, icon_name=1)
        column.set_resizable(True)
        self.playlist_songs.append_column(column)

        self.playlist_songs.append_column(SongListColumn("TITLE", 2, bold=True))
        self.playlist_songs.append_column(SongListColumn("ALBUM", 3))
        self.playlist_songs.append_column(SongListColumn("ARTIST", 4))
        self.playlist_songs.append_column(
            SongListColumn("DURATION", 5, align=1, width=40)
        )

        self.playlist_songs.connect("row-activated", self.on_song_activated)
        self.playlist_songs.connect("button-press-event", self.on_song_button_press)

        # Set up drag-and-drop on the song list for editing the order of the
        # playlist.
        self.playlist_song_store.connect(
            "row-inserted", self.on_playlist_model_row_move
        )
        self.playlist_song_store.connect("row-deleted", self.on_playlist_model_row_move)

        self.playlist_song_scroll_window.add(self.playlist_songs)

        self.playlist_box.pack_start(self.playlist_song_scroll_window, True, True, 0)
        self.add(self.playlist_box)

        playlist_view_spinner = Gtk.Spinner(active=True)
        playlist_view_spinner.start()

        self.playlist_view_loading_box = Gtk.Alignment(
            name="playlist-view-overlay", xalign=0.5, yalign=0.5, xscale=0.1, yscale=0.1
        )
        self.playlist_view_loading_box.add(playlist_view_spinner)
        self.add_overlay(self.playlist_view_loading_box)

    update_playlist_view_order_token = 0

    def update(self, app_config: AppConfiguration, force: bool = False):
        # Deselect everything if switching online to offline.
        if self.offline_mode != app_config.offline_mode:
            self.playlist_songs.get_selection().unselect_all()

        self.offline_mode = app_config.offline_mode
        if app_config.state.selected_playlist_id is None:
            self.playlist_box.hide()
            self.playlist_view_loading_box.hide()
        else:
            self.update_playlist_view_order_token += 1
            self.playlist_box.show()
            self.update_playlist_view(
                app_config.state.selected_playlist_id,
                app_config=app_config,
                force=force,
                order_token=self.update_playlist_view_order_token,
            )
            self.download_all_button.set_sensitive(not app_config.offline_mode)
            self.playlist_edit_button.set_sensitive(not app_config.offline_mode)
            self.view_refresh_button.set_sensitive(not app_config.offline_mode)

    _current_song_ids: List[str] = []

    @util.async_callback(
        AdapterManager.get_playlist_details,
        before_download=lambda self: self.show_loading_all(),
        on_failure=lambda self, e: self.hide_loading_all(),
    )
    def update_playlist_view(
        self,
        playlist: API.Playlist,
        app_config: AppConfiguration = None,
        force: bool = False,
        order_token: int = None,
        is_partial: bool = False,
    ):
        if self.update_playlist_view_order_token != order_token:
            return

        # If the selected playlist has changed, then clear the selections in
        # the song list.
        if self.playlist_id != playlist.id:
            self.playlist_songs.get_selection().unselect_all()

        self.playlist_id = playlist.id

        if app_config:
            self.playlist_details_expanded = app_config.state.playlist_details_expanded

        up_down = "up" if self.playlist_details_expanded else "down"
        self.expand_collapse_button.set_icon(f"pan-{up_down}-symbolic")
        self.expand_collapse_button.set_tooltip_text(
            "Collapse" if self.playlist_details_expanded else "Expand"
        )

        # Update the info display.
        self.playlist_name.set_markup(f"<b>{playlist.name}</b>")
        self.playlist_name.set_tooltip_text(playlist.name)

        if self.playlist_details_expanded:
            self.playlist_artwork.get_style_context().remove_class("collapsed")
            self.playlist_name.get_style_context().remove_class("collapsed")
            self.playlist_box.show_all()
            self.playlist_indicator.set_markup("PLAYLIST")

            if playlist.comment:
                self.playlist_comment.set_text(playlist.comment)
                self.playlist_comment.set_tooltip_text(playlist.comment)
                self.playlist_comment.show()
            else:
                self.playlist_comment.hide()

            self.playlist_stats.set_markup(self._format_stats(playlist))
        else:
            self.playlist_artwork.get_style_context().add_class("collapsed")
            self.playlist_name.get_style_context().add_class("collapsed")
            self.playlist_box.show_all()
            self.playlist_indicator.hide()
            self.playlist_comment.hide()
            self.playlist_stats.hide()

        # Update the artwork.
        self.update_playlist_artwork(playlist.cover_art, order_token=order_token)

        for c in self.error_container.get_children():
            self.error_container.remove(c)
        if is_partial:
            has_data = len(playlist.songs) > 0
            load_error = LoadError(
                "Playlist data",
                "load playlist details",
                has_data=has_data,
                offline_mode=self.offline_mode,
            )
            self.error_container.pack_start(load_error, True, True, 0)
            self.error_container.show_all()
            if not has_data:
                self.playlist_song_scroll_window.hide()
        else:
            self.error_container.hide()
            self.playlist_song_scroll_window.show()

        # Update the song list model. This requires some fancy diffing to
        # update the list.
        self.editing_playlist_song_list = True

        # This doesn't look efficient, since it's doing a ton of passses over the data,
        # but there is some annoying memory overhead for generating the stores to diff,
        # so we are short-circuiting by checking to see if any of the the IDs have
        # changed.
        #
        # The entire algorithm ends up being O(2n), but the first loop is very tight,
        # and the expensive parts of the second loop are avoided if the IDs haven't
        # changed.
        song_ids, songs = [], []
        if len(self._current_song_ids) != len(playlist.songs):
            force = True

        for i, c in enumerate(playlist.songs):
            if i >= len(self._current_song_ids) or c.id != self._current_song_ids[i]:
                force = True
            song_ids.append(c.id)
            songs.append(c)

        new_songs_store = []
        can_play_any_song = False
        cached_status_icons = ("folder-download-symbolic", "view-pin-symbolic")

        if force:
            self._current_song_ids = song_ids

            # Regenerate the store from the actual song data (this is more expensive
            # because when coming from the cache, we are doing 2N fk requests to
            # albums).
            for status_icon, song in zip(
                util.get_cached_status_icons(song_ids),
                [cast(API.Song, s) for s in songs],
            ):
                playable = not self.offline_mode or status_icon in cached_status_icons
                can_play_any_song |= playable
                new_songs_store.append(
                    [
                        playable,
                        status_icon,
                        song.title,
                        album.name if (album := song.album) else None,
                        artist.name if (artist := song.artist) else None,
                        util.format_song_duration(song.duration),
                        song.id,
                    ]
                )
        else:
            # Just update the clickable state and download state.
            for status_icon, song_model in zip(
                util.get_cached_status_icons(song_ids), self.playlist_song_store
            ):
                playable = not self.offline_mode or status_icon in cached_status_icons
                can_play_any_song |= playable
                new_songs_store.append([playable, status_icon, *song_model[2:]])

        util.diff_song_store(self.playlist_song_store, new_songs_store)

        self.play_all_button.set_sensitive(can_play_any_song)
        self.shuffle_all_button.set_sensitive(can_play_any_song)

        self.editing_playlist_song_list = False

        self.playlist_view_loading_box.hide()
        self.playlist_action_buttons.show_all()

    @util.async_callback(
        partial(AdapterManager.get_cover_art_uri, scheme="file"),
        before_download=lambda self: self.playlist_artwork.set_loading(True),
        on_failure=lambda self, e: self.playlist_artwork.set_loading(False),
    )
    def update_playlist_artwork(
        self,
        cover_art_filename: str,
        app_config: AppConfiguration,
        force: bool = False,
        order_token: int = None,
        is_partial: bool = False,
    ):
        if self.update_playlist_view_order_token != order_token:
            return

        self.playlist_artwork.set_from_file(cover_art_filename)
        self.playlist_artwork.set_loading(False)

        if self.playlist_details_expanded:
            self.playlist_artwork.set_image_size(200)
        else:
            self.playlist_artwork.set_image_size(70)

    # Event Handlers
    # =========================================================================
    def on_view_refresh_click(self, _):
        self.update_playlist_view(
            self.playlist_id,
            force=True,
            order_token=self.update_playlist_view_order_token,
        )

    def on_playlist_edit_button_click(self, _):
        assert self.playlist_id
        playlist = AdapterManager.get_playlist_details(self.playlist_id).result()
        dialog = EditPlaylistDialog(self.get_toplevel(), playlist)
        playlist_deleted = False

        result = dialog.run()
        # Using ResponseType.NO as the delete event.
        if result not in (Gtk.ResponseType.APPLY, Gtk.ResponseType.NO):
            dialog.destroy()
            return

        if result == Gtk.ResponseType.APPLY:
            AdapterManager.update_playlist(self.playlist_id, **dialog.get_data())
        elif result == Gtk.ResponseType.NO:
            # Delete the playlist.
            confirm_dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.NONE,
                text="Confirm deletion",
            )
            confirm_dialog.add_buttons(
                Gtk.STOCK_DELETE,
                Gtk.ResponseType.YES,
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
            )
            confirm_dialog.format_secondary_markup(
                f'Are you sure you want to delete the "{playlist.name}" playlist?'
            )
            result = confirm_dialog.run()
            confirm_dialog.destroy()
            if result == Gtk.ResponseType.YES:
                AdapterManager.delete_playlist(self.playlist_id)
                playlist_deleted = True
            else:
                # In this case, we don't want to do any invalidation of
                # anything.
                dialog.destroy()
                return

        # Force a re-fresh of the view
        self.emit(
            "refresh-window",
            {"selected_playlist_id": None if playlist_deleted else self.playlist_id},
            True,
        )
        dialog.destroy()

    def on_playlist_list_download_all_button_click(self, _):
        def download_state_change(song_id: str):
            GLib.idle_add(
                lambda: self.update_playlist_view(
                    self.playlist_id, order_token=self.update_playlist_view_order_token
                )
            )

        song_ids = [s[-1] for s in self.playlist_song_store]
        AdapterManager.batch_download_songs(
            song_ids,
            before_download=download_state_change,
            on_song_download_complete=download_state_change,
        )

    def on_play_all_clicked(self, _):
        self.emit(
            "song-clicked",
            0,
            [m[-1] for m in self.playlist_song_store],
            {"force_shuffle_state": False, "active_playlist_id": self.playlist_id},
        )

    def on_shuffle_all_button(self, _):
        self.emit(
            "song-clicked",
            randint(0, len(self.playlist_song_store) - 1),
            [m[-1] for m in self.playlist_song_store],
            {"force_shuffle_state": True, "active_playlist_id": self.playlist_id},
        )

    def on_expand_collapse_click(self, _):
        self.emit(
            "refresh-window",
            {"playlist_details_expanded": not self.playlist_details_expanded},
            False,
        )

    def on_song_activated(self, _, idx: Gtk.TreePath, col: Any):
        if not self.playlist_song_store[idx[0]][0]:
            return
        # The song ID is in the last column of the model.
        self.emit(
            "song-clicked",
            idx.get_indices()[0],
            [m[-1] for m in self.playlist_song_store],
            {"active_playlist_id": self.playlist_id},
        )

    def on_song_button_press(self, tree: Gtk.TreeView, event: Gdk.EventButton) -> bool:
        if event.button == 3:  # Right click
            clicked_path = tree.get_path_at_pos(event.x, event.y)
            if not clicked_path:
                return False

            store, paths = tree.get_selection().get_selected_rows()
            allow_deselect = False

            def on_download_state_change(song_id: str):
                GLib.idle_add(
                    lambda: self.update_playlist_view(
                        self.playlist_id,
                        order_token=self.update_playlist_view_order_token,
                    )
                )

            # Use the new selection instead of the old one for calculating what
            # to do the right click on.
            if clicked_path[0] not in paths:
                paths = [clicked_path[0]]
                allow_deselect = True

            song_ids = [self.playlist_song_store[p][-1] for p in paths]

            # Used to adjust for the header row.
            bin_coords = tree.convert_tree_to_bin_window_coords(event.x, event.y)
            widget_coords = tree.convert_tree_to_widget_coords(event.x, event.y)

            def on_remove_songs_click(_):
                assert self.playlist_id
                delete_idxs = {p.get_indices()[0] for p in paths}
                new_song_ids = [
                    model[-1]
                    for i, model in enumerate(self.playlist_song_store)
                    if i not in delete_idxs
                ]
                AdapterManager.update_playlist(
                    playlist_id=self.playlist_id, song_ids=new_song_ids
                ).result()
                self.update_playlist_view(
                    self.playlist_id,
                    force=True,
                    order_token=self.update_playlist_view_order_token,
                )

            remove_text = (
                "Remove " + util.pluralize("song", len(song_ids)) + " from playlist"
            )
            util.show_song_popover(
                song_ids,
                event.x,
                event.y + abs(bin_coords.by - widget_coords.wy),
                tree,
                self.offline_mode,
                on_download_state_change=on_download_state_change,
                on_remove_downloads_click=(
                    lambda: (
                        self.offline_mode
                        and self.playlist_songs.get_selection().unselect_all()
                    )
                ),
                extra_menu_items=[
                    (
                        Gtk.ModelButton(
                            text=remove_text, sensitive=not self.offline_mode
                        ),
                        on_remove_songs_click,
                    )
                ],
                on_playlist_state_change=lambda: self.emit("refresh-window", {}, True),
            )

            # If the click was on a selected row, don't deselect anything.
            if not allow_deselect:
                return True

        return False

    def on_playlist_model_row_move(self, *args):
        # If we are programatically editing the song list, don't do anything.
        if self.editing_playlist_song_list:
            return

        # We get both a delete and insert event, I think it's deterministic
        # which one comes first, but just in case, we have this
        # reordering_playlist_song_list flag.
        if self.reordering_playlist_song_list:
            self._update_playlist_order(self.playlist_id)
            self.reordering_playlist_song_list = False
        else:
            self.reordering_playlist_song_list = True

    # Helper Methods
    # =========================================================================
    def show_loading_all(self):
        self.playlist_artwork.set_loading(True)
        self.playlist_view_loading_box.show_all()

    def hide_loading_all(self):
        self.playlist_artwork.set_loading(False)
        self.playlist_view_loading_box.hide()

    def make_label(self, text: str = None, name: str = None, **params) -> Gtk.Label:
        return Gtk.Label(
            label=text,
            name=name,
            halign=Gtk.Align.START,
            ellipsize=Pango.EllipsizeMode.END,
            **params,
        )

    @util.async_callback(AdapterManager.get_playlist_details)
    def _update_playlist_order(
        self,
        playlist: API.Playlist,
        app_config: AppConfiguration,
        **kwargs,
    ):
        self.playlist_view_loading_box.show_all()
        update_playlist_future = AdapterManager.update_playlist(
            playlist.id, song_ids=[s[-1] for s in self.playlist_song_store]
        )

        update_playlist_future.add_done_callback(
            lambda f: GLib.idle_add(
                lambda: self.update_playlist_view(
                    playlist.id,
                    force=True,
                    order_token=self.update_playlist_view_order_token,
                )
            )
        )

    def _format_stats(self, playlist: API.Playlist) -> str:
        created_date_text = ""
        if playlist.created:
            created_date_text = f" on {playlist.created.strftime('%B %d, %Y')}"
        created_text = f"Created by {playlist.owner}{created_date_text}"

        lines = [
            util.dot_join(
                created_text,
                f"{'Not v' if not playlist.public else 'V'}isible to others",
            ),
            util.dot_join(
                "{} {}".format(
                    playlist.song_count,
                    util.pluralize("song", playlist.song_count or 0),
                ),
                util.format_sequence_duration(playlist.duration),
            ),
        ]
        return "\n".join(lines)
