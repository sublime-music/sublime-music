import logging
import os
import random
import shutil
import sys
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlparse

import bleach

try:
    import osxmmkeys

    tap_imported = True
except Exception:
    tap_imported = False

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

try:
    import gi

    gi.require_version("Notify", "0.7")
    from gi.repository import Notify

    glib_notify_exists = True
except Exception:
    # I really don't care what kind of exception it is, all that matters is the
    # import failed for some reason.
    logging.warning(
        "Unable to import Notify from GLib. Notifications will be disabled."
    )
    glib_notify_exists = False

from .adapters import (
    AdapterManager,
    AlbumSearchQuery,
    CacheMissError,
    DownloadProgress,
    Result,
    SongCacheStatus,
)
from .adapters.api_objects import Playlist, PlayQueue, Song
from .config import AppConfiguration, ProviderConfiguration
from .dbus import dbus_propagate, DBusManager
from .players import PlayerDeviceEvent, PlayerEvent, PlayerManager
from .ui.configure_provider import ConfigureProviderDialog
from .ui.main import MainWindow
from .ui.state import RepeatType, UIState
from .util import resolve_path


class SublimeMusicApp(Gtk.Application):
    def __init__(self, config_file: Path):
        super().__init__(application_id="app.sublimemusic.SublimeMusic")
        if glib_notify_exists:
            Notify.init("Sublime Music")

        self.window: Optional[Gtk.Window] = None
        self.app_config = AppConfiguration.load_from_file(config_file)
        self.dbus_manager: Optional[DBusManager] = None

        self.connect("shutdown", self.on_app_shutdown)

    player_manager: Optional[PlayerManager] = None
    exiting: bool = False

    def do_startup(self):
        Gtk.Application.do_startup(self)

        def add_action(name: str, fn: Callable, parameter_type: str = None):
            """Registers an action with the application."""
            if type(parameter_type) == str:
                parameter_type = GLib.VariantType(parameter_type)
            action = Gio.SimpleAction.new(name, parameter_type)
            action.connect("activate", fn)
            self.add_action(action)

        # Add action for menu items.
        add_action("add-new-music-provider", self.on_add_new_music_provider)
        add_action("edit-current-music-provider", self.on_edit_current_music_provider)
        add_action(
            "switch-music-provider", self.on_switch_music_provider, parameter_type="s"
        )
        add_action(
            "remove-music-provider", self.on_remove_music_provider, parameter_type="s"
        )

        # Add actions for player controls
        add_action("play-pause", self.on_play_pause)
        add_action("next-track", self.on_next_track)
        add_action("prev-track", self.on_prev_track)
        add_action("repeat-press", self.on_repeat_press)
        add_action("shuffle-press", self.on_shuffle_press)

        # Navigation actions.
        add_action("play-next", self.on_play_next, parameter_type="as")
        add_action("add-to-queue", self.on_add_to_queue, parameter_type="as")
        add_action("go-to-album", self.on_go_to_album, parameter_type="s")
        add_action("go-to-artist", self.on_go_to_artist, parameter_type="s")
        add_action("browse-to", self.browse_to, parameter_type="s")
        add_action("go-to-playlist", self.on_go_to_playlist, parameter_type="s")

        add_action("go-online", self.on_go_online)
        add_action("refresh-devices", self.on_refresh_devices)
        add_action(
            "refresh-window",
            lambda *a: self.on_refresh_window(None, {}, True),
        )
        add_action("mute-toggle", self.on_mute_toggle)
        add_action(
            "update-play-queue-from-server",
            lambda a, p: self.update_play_state_from_server(),
        )

        if tap_imported:
            self.tap = osxmmkeys.Tap()
            self.tap.on("play_pause", self.on_play_pause)
            self.tap.on("next_track", self.on_next_track)
            self.tap.on("prev_track", self.on_prev_track)
            self.tap.start()

    def do_activate(self):
        # We only allow a single window and raise any existing ones
        if self.window:
            self.window.present()
            return

        # Configure Icons
        default_icon_theme = Gtk.IconTheme.get_default()
        for adapter in AdapterManager.available_adapters:
            if icon_dir := adapter.get_ui_info().icon_dir:
                default_icon_theme.append_search_path(str(icon_dir))

        icon_dirs = [resolve_path("ui/icons"), resolve_path("adapters/icons")]
        for icon_dir in icon_dirs:
            default_icon_theme.append_search_path(str(icon_dir))

        # Windows are associated with the application when the last one is
        # closed the application shuts down.
        self.window = MainWindow(application=self, title="Sublime Music")

        # Configure the CSS provider so that we can style elements on the
        # window.
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(str(resolve_path("ui/app_styles.css")))
        context = Gtk.StyleContext()
        screen = Gdk.Screen.get_default()
        context.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

        self.window.show_all()
        self.window.present()

        # Load the state for the server, if it exists.
        self.app_config.load_state()

        # If there is no current provider, use the first one if there are any
        # configured, and if none are configured, then show the dialog to create a new
        # one.
        if self.app_config.provider is None:
            if len(self.app_config.providers) == 0:
                self.show_configure_servers_dialog()

                # If they didn't add one with the dialog, close the window.
                if len(self.app_config.providers) == 0:
                    self.window.close()
                    return

        AdapterManager.reset(self.app_config, self.on_song_download_progress)

        # Connect after we know there's a server configured.
        self.window.stack.connect("notify::visible-child", self.on_stack_change)
        self.window.connect("song-clicked", self.on_song_clicked)
        self.window.connect("songs-removed", self.on_songs_removed)
        self.window.connect("refresh-window", self.on_refresh_window)
        self.window.connect("notification-closed", self.on_notification_closed)
        self.window.connect("go-to", self.on_window_go_to)
        self.window.connect("key-press-event", self.on_window_key_press)
        self.window.player_controls.connect("song-scrub", self.on_song_scrub)
        self.window.player_controls.connect("device-update", self.on_device_update)
        self.window.player_controls.connect("volume-change", self.on_volume_change)

        # Configure the players
        self.last_play_queue_update = timedelta(0)
        self.loading_state = False
        self.should_scrobble_song = False

        def on_timepos_change(value: Optional[float]):
            if (
                self.loading_state
                or not self.window
                or not self.app_config.state.current_song
            ):
                return

            if value is None:
                self.last_play_queue_update = timedelta(0)
                return

            self.app_config.state.song_progress = timedelta(seconds=value)
            GLib.idle_add(
                self.window.player_controls.update_scrubber,
                self.app_config.state.song_progress,
                self.app_config.state.current_song.duration,
                self.app_config.state.song_stream_cache_progress,
            )

            if (self.last_play_queue_update + timedelta(15)).total_seconds() <= value:
                self.save_play_queue()

            if (
                value > 5
                and self.should_scrobble_song
                and AdapterManager.can_scrobble_song()
            ):
                AdapterManager.scrobble_song(self.app_config.state.current_song)
                self.should_scrobble_song = False

        def on_track_end():
            at_end = (
                self.app_config.state.current_song_index
                == len(self.app_config.state.play_queue) - 1
            )
            no_repeat = self.app_config.state.repeat_type == RepeatType.NO_REPEAT
            if at_end and no_repeat:
                self.app_config.state.playing = False
                self.app_config.state.current_song_index = -1
                self.update_window()
                return

            GLib.idle_add(self.on_next_track)

        def on_player_event(event: PlayerEvent):
            if event.type == PlayerEvent.EventType.PLAY_STATE_CHANGE:
                assert event.playing is not None
                self.app_config.state.playing = event.playing
                if self.dbus_manager:
                    self.dbus_manager.property_diff()
                self.update_window()

            elif event.type == PlayerEvent.EventType.VOLUME_CHANGE:
                assert event.volume is not None
                self.app_config.state.volume = event.volume
                if self.dbus_manager:
                    self.dbus_manager.property_diff()
                self.update_window()

            elif event.type == PlayerEvent.EventType.STREAM_CACHE_PROGRESS_CHANGE:
                if (
                    self.loading_state
                    or not self.window
                    or not self.app_config.state.current_song
                    or event.stream_cache_duration is None
                ):
                    return
                self.app_config.state.song_stream_cache_progress = timedelta(
                    seconds=event.stream_cache_duration
                )
                GLib.idle_add(
                    self.window.player_controls.update_scrubber,
                    self.app_config.state.song_progress,
                    self.app_config.state.current_song.duration,
                    self.app_config.state.song_stream_cache_progress,
                )

            elif event.type == PlayerEvent.EventType.DISCONNECT:
                assert self.player_manager
                self.app_config.state.current_device = "this device"
                self.player_manager.set_current_device_id(
                    self.app_config.state.current_device
                )
                self.player_manager.set_volume(self.app_config.state.volume)
                self.update_window()

        def player_device_change_callback(event: PlayerDeviceEvent):
            assert self.player_manager
            state_device = self.app_config.state.current_device

            if event.delta == PlayerDeviceEvent.Delta.ADD:
                # If the device added is the one that's supposed to be active, activate
                # it and set the volume.
                if event.id == state_device:
                    self.player_manager.set_current_device_id(
                        self.app_config.state.current_device
                    )
                    self.player_manager.set_volume(self.app_config.state.volume)
                    self.app_config.state.connected_device_name = event.name
                    self.app_config.state.connecting_to_device = False
                self.app_config.state.available_players[event.player_type].add(
                    (event.id, event.name)
                )

            elif event.delta == PlayerDeviceEvent.Delta.REMOVE:
                if state_device == event.id:
                    self.player_manager.pause()
                self.app_config.state.available_players[event.player_type].remove(
                    (event.id, event.name)
                )

            self.update_window()

        self.app_config.state.connecting_to_device = True

        def check_if_connected():
            if not self.app_config.state.connecting_to_device:
                return
            self.app_config.state.current_device = "this device"
            self.app_config.state.connecting_to_device = False
            self.player_manager.set_current_device_id(
                self.app_config.state.current_device
            )
            self.update_window()

        self.player_manager = PlayerManager(
            on_timepos_change,
            on_track_end,
            on_player_event,
            lambda *a: GLib.idle_add(player_device_change_callback, *a),
            self.app_config.player_config,
        )
        GLib.timeout_add(10000, check_if_connected)

        # Update after Adapter Initial Sync
        def after_initial_sync(_):
            self.update_window()

            # Prompt to load the play queue from the server.
            if AdapterManager.can_get_play_queue():
                self.update_play_state_from_server(prompt_confirm=True)

            # Get the playlists, just so that we don't have tons of cache misses from
            # DBus trying to get the playlists.
            if AdapterManager.can_get_playlists():
                AdapterManager.get_playlists()

        inital_sync_result = AdapterManager.initial_sync()
        inital_sync_result.add_done_callback(after_initial_sync)

        # Send out to the bus that we exist.
        if self.dbus_manager:
            self.dbus_manager.property_diff()

    # ########## DBUS MANAGMENT ########## #
    def do_dbus_register(self, connection: Gio.DBusConnection, path: str) -> bool:
        self.dbus_manager = DBusManager(
            connection,
            self.on_dbus_method_call,
            self.on_dbus_set_property,
            lambda: (self.app_config, self.player_manager),
        )
        return True

    def on_dbus_method_call(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        path: str,
        interface: str,
        method: str,
        params: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ):
        def seek_fn(offset: float):
            if not self.app_config.state.current_song:
                return
            new_seconds = self.app_config.state.song_progress + timedelta(
                microseconds=offset
            )

            # This should not ever happen. The current_song should always have
            # a duration, but the Child object has `duration` optional because
            # it could be a directory.
            assert self.app_config.state.current_song.duration is not None
            self.on_song_scrub(
                None,
                (
                    new_seconds.total_seconds()
                    / self.app_config.state.current_song.duration.total_seconds()
                )
                * 100,
            )

        def set_pos_fn(track_id: str, position: float = 0):
            if self.app_config.state.playing:
                self.on_play_pause()
            pos_seconds = timedelta(microseconds=position)
            self.app_config.state.song_progress = pos_seconds
            track_id, occurrence = track_id.split("/")[-2:]

            # Find the (N-1)th time that the track id shows up in the list. (N
            # is the -*** suffix on the track id.)
            song_index = [
                i
                for i, x in enumerate(self.app_config.state.play_queue)
                if x == track_id
            ][int(occurrence) or 0]

            self.play_song(song_index)

        def get_tracks_metadata(track_ids: List[str]) -> GLib.Variant:
            if not self.dbus_manager:
                return

            if len(track_ids) == 0:
                # We are lucky, just return an empty list.
                return GLib.Variant("(aa{sv})", ([],))

            # Have to calculate all of the metadatas so that we can deal with
            # repeat song IDs.
            metadatas: Iterable[Any] = [
                self.dbus_manager.get_mpris_metadata(
                    i,
                    self.app_config.state.play_queue,
                )
                for i in range(len(self.app_config.state.play_queue))
            ]

            # Get rid of all of the tracks that were not requested.
            metadatas = list(
                filter(lambda m: m["mpris:trackid"] in track_ids, metadatas)
            )

            assert len(metadatas) == len(track_ids)

            # Sort them so they get returned in the same order as they were
            # requested.
            metadatas = sorted(
                metadatas, key=lambda m: track_ids.index(m["mpris:trackid"])
            )

            # Turn them into dictionaries that can actually be serialized into
            # a GLib.Variant.
            metadatas = map(
                lambda m: {k: DBusManager.to_variant(v) for k, v in m.items()},
                metadatas,
            )

            return GLib.Variant("(aa{sv})", (list(metadatas),))

        def activate_playlist(playlist_id: str):
            playlist_id = playlist_id.split("/")[-1]
            playlist = AdapterManager.get_playlist_details(playlist_id).result()

            # Calculate the song id to play.
            song_idx = 0
            if self.app_config.state.shuffle_on:
                song_idx = random.randint(0, len(playlist.songs) - 1)

            self.on_song_clicked(
                None,
                song_idx,
                tuple(s.id for s in playlist.songs),
                {"active_playlist_id": playlist_id},
            )

        def get_playlists(
            index: int,
            max_count: int,
            order: str,
            reverse_order: bool,
        ) -> GLib.Variant:
            playlists_result = AdapterManager.get_playlists()
            if not playlists_result.data_is_available:
                # We don't want to wait for the response in this case, so just
                # return an empty array.
                return GLib.Variant("(a(oss))", ([],))

            playlists = list(playlists_result.result())

            sorters = {
                "Alphabetical": lambda p: p.name,
                "Created": lambda p: p.created,
                "Modified": lambda p: p.changed,
            }
            playlists.sort(
                key=sorters.get(order, lambda p: p),
                reverse=reverse_order,
            )

            def make_playlist_tuple(p: Playlist) -> GLib.Variant:
                cover_art_filename = AdapterManager.get_cover_art_uri(
                    p.cover_art,
                    "file",
                    allow_download=False,
                ).result()
                return (f"/playlist/{p.id}", p.name, cover_art_filename or "")

            return GLib.Variant(
                "(a(oss))",
                (
                    [
                        make_playlist_tuple(p)
                        for p in playlists[index : (index + max_count)]
                    ],
                ),
            )

        def play():
            if not self.app_config.state.playing:
                self.on_play_pause()

        def pause():
            if self.app_config.state.playing:
                self.on_play_pause()

        method_call_map: Dict[str, Dict[str, Any]] = {
            "org.mpris.MediaPlayer2": {
                "Raise": self.window and self.window.present,
                "Quit": self.window and self.window.destroy,
            },
            "org.mpris.MediaPlayer2.Player": {
                "Next": self.on_next_track,
                "Previous": self.on_prev_track,
                "Pause": pause,
                "PlayPause": self.on_play_pause,
                "Stop": pause,
                "Play": play,
                "Seek": seek_fn,
                "SetPosition": set_pos_fn,
            },
            "org.mpris.MediaPlayer2.TrackList": {
                "GoTo": set_pos_fn,
                "GetTracksMetadata": get_tracks_metadata,
                # 'RemoveTrack': remove_track,
            },
            "org.mpris.MediaPlayer2.Playlists": {
                "ActivatePlaylist": activate_playlist,
                "GetPlaylists": get_playlists,
            },
        }
        method_fn = method_call_map.get(interface, {}).get(method)
        if method_fn is None:
            logging.warning(f"Unknown/unimplemented method: {interface}.{method}.")
        invocation.return_value(method_fn(*params) if callable(method_fn) else None)

    def on_dbus_set_property(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        path: str,
        interface: str,
        property_name: str,
        value: GLib.Variant,
    ):
        def change_loop(new_loop_status: GLib.Variant):
            self.app_config.state.repeat_type = RepeatType.from_mpris_loop_status(
                new_loop_status.get_string()
            )
            self.update_window()

        def set_shuffle(new_val: GLib.Variant):
            if new_val.get_boolean() != self.app_config.state.shuffle_on:
                self.on_shuffle_press(None, None)

        def set_volume(new_val: GLib.Variant):
            self.on_volume_change(None, new_val.get_double() * 100)

        setter_map: Dict[str, Dict[str, Any]] = {
            "org.mpris.MediaPlayer2.Player": {
                "LoopStatus": change_loop,
                "Rate": lambda _: None,
                "Shuffle": set_shuffle,
                "Volume": set_volume,
            }
        }

        setter = setter_map.get(interface, {}).get(property_name)
        if setter is None:
            logging.warning("Set: Unknown property: {property_name}.")
            return
        if callable(setter):
            setter(value)

    # ########## ACTION HANDLERS ########## #
    @dbus_propagate()
    def on_refresh_window(self, _, state_updates: Dict[str, Any], force: bool = False):
        if settings := state_updates.get("__settings__"):
            for k, v in settings.items():
                setattr(self.app_config, k, v)
            if (offline_mode := settings.get("offline_mode")) is not None:
                AdapterManager.on_offline_mode_change(offline_mode)

            del state_updates["__settings__"]
            self.app_config.save()

        if player_setting := state_updates.get("__player_setting__"):
            player_name, option_name, value = player_setting
            self.app_config.player_config[player_name][option_name] = value
            del state_updates["__player_setting__"]
            if pm := self.player_manager:
                pm.change_settings(self.app_config.player_config)
            self.app_config.save()

        for k, v in state_updates.items():
            setattr(self.app_config.state, k, v)
        self.update_window(force=force)

    def on_notification_closed(self, _):
        self.app_config.state.current_notification = None
        self.update_window()

    def on_add_new_music_provider(self, *args):
        self.show_configure_servers_dialog()

    def on_edit_current_music_provider(self, *args):
        self.show_configure_servers_dialog(self.app_config.provider.clone())

    def on_switch_music_provider(self, _, provider_id: GLib.Variant):
        if self.app_config.state.playing:
            self.on_play_pause()
        self.app_config.save()
        self.app_config.current_provider_id = provider_id.get_string()
        self.reset_state()
        self.app_config.save()

    def on_remove_music_provider(self, _, provider_id: GLib.Variant):
        provider = self.app_config.providers[provider_id.get_string()]
        confirm_dialog = Gtk.MessageDialog(
            transient_for=self.window,
            message_type=Gtk.MessageType.WARNING,
            buttons=(
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_DELETE,
                Gtk.ResponseType.YES,
            ),
            text=f"Are you sure you want to delete the {provider.name} music provider?",
        )
        confirm_dialog.format_secondary_markup(
            "Deleting this music provider will delete all cached songs and metadata "
            "associated with this provider."
        )
        if confirm_dialog.run() == Gtk.ResponseType.YES:
            assert self.app_config.cache_location
            provider_dir = self.app_config.cache_location.joinpath(provider.id)
            shutil.rmtree(str(provider_dir), ignore_errors=True)
            del self.app_config.providers[provider.id]

        confirm_dialog.destroy()

    def on_window_go_to(self, win: Any, action: str, value: str):
        {
            "album": self.on_go_to_album,
            "artist": self.on_go_to_artist,
            "playlist": self.on_go_to_playlist,
        }[action](None, GLib.Variant("s", value))

    @dbus_propagate()
    def on_play_pause(self, *args):
        if self.app_config.state.current_song_index < 0:
            return

        self.app_config.state.playing = not self.app_config.state.playing

        if self.player_manager.song_loaded and (
            self.player_manager.current_song == self.app_config.state.current_song
        ):
            self.player_manager.toggle_play()
            self.save_play_queue()
        else:
            # This is from a restart, start playing the file.
            self.play_song(self.app_config.state.current_song_index)

        self.update_window()

    def on_next_track(self, *args):
        if self.app_config.state.current_song is None:
            # This may happen due to DBUS, ignore.
            return
        # Handle song repeating
        if self.app_config.state.repeat_type == RepeatType.REPEAT_SONG:
            song_index_to_play = self.app_config.state.current_song_index
        # Wrap around the play queue if at the end.
        elif (
            self.app_config.state.current_song_index
            == len(self.app_config.state.play_queue) - 1
        ):
            # This may happen due to D-Bus.
            if self.app_config.state.repeat_type == RepeatType.NO_REPEAT:
                return
            song_index_to_play = 0
        else:
            song_index_to_play = self.app_config.state.current_song_index + 1

        self.app_config.state.current_song_index = song_index_to_play
        self.app_config.state.song_progress = timedelta(0)
        if self.app_config.state.playing:
            self.play_song(song_index_to_play, reset=True)
        else:
            self.update_window()

    def on_prev_track(self, *args):
        if self.app_config.state.current_song is None:
            # This may happen due to DBUS, ignore.
            return
        # Go back to the beginning of the song if we are past 5 seconds.
        # Otherwise, go to the previous song.
        no_repeat = self.app_config.state.repeat_type == RepeatType.NO_REPEAT
        if self.app_config.state.repeat_type == RepeatType.REPEAT_SONG:
            song_index_to_play = self.app_config.state.current_song_index
        elif self.app_config.state.song_progress.total_seconds() < 5:
            if self.app_config.state.current_song_index == 0 and no_repeat:
                song_index_to_play = 0
            else:
                song_index_to_play = (
                    self.app_config.state.current_song_index - 1
                ) % len(self.app_config.state.play_queue)
        else:
            # Go back to the beginning of the song.
            song_index_to_play = self.app_config.state.current_song_index

        self.app_config.state.current_song_index = song_index_to_play
        self.app_config.state.song_progress = timedelta(0)
        if self.player_manager.playing:
            self.play_song(
                song_index_to_play,
                reset=True,
                # search backwards for a song to play if offline
                playable_song_search_direction=-1,
            )
        else:
            self.update_window()

    @dbus_propagate()
    def on_repeat_press(self, *args):
        # Cycle through the repeat types.
        new_repeat_type = RepeatType((self.app_config.state.repeat_type.value + 1) % 3)
        self.app_config.state.repeat_type = new_repeat_type
        self.update_window()

    @dbus_propagate()
    def on_shuffle_press(self, *args):
        if self.app_config.state.shuffle_on:
            # Revert to the old play queue.
            old_play_queue_copy = self.app_config.state.old_play_queue
            self.app_config.state.current_song_index = old_play_queue_copy.index(
                self.app_config.state.current_song.id
            )
            self.app_config.state.play_queue = old_play_queue_copy
        else:
            self.app_config.state.old_play_queue = self.app_config.state.play_queue

            mutable_play_queue = list(self.app_config.state.play_queue)

            # Remove the current song, then shuffle and put the song back.
            song_id = self.app_config.state.current_song.id
            del mutable_play_queue[self.app_config.state.current_song_index]
            random.shuffle(mutable_play_queue)
            self.app_config.state.play_queue = (song_id,) + tuple(mutable_play_queue)
            self.app_config.state.current_song_index = 0

        self.app_config.state.shuffle_on = not self.app_config.state.shuffle_on
        self.update_window()

    @dbus_propagate()
    def on_play_next(self, action: Any, song_ids: GLib.Variant):
        song_ids = tuple(song_ids)
        if self.app_config.state.current_song is None:
            insert_at = 0
        else:
            insert_at = self.app_config.state.current_song_index + 1

        self.app_config.state.play_queue = (
            self.app_config.state.play_queue[:insert_at]
            + song_ids
            + self.app_config.state.play_queue[insert_at:]
        )
        self.app_config.state.old_play_queue += song_ids
        self.update_window()

    @dbus_propagate()
    def on_add_to_queue(self, action: Any, song_ids: GLib.Variant):
        song_ids = tuple(song_ids)
        self.app_config.state.play_queue += tuple(song_ids)
        self.app_config.state.old_play_queue += tuple(song_ids)
        self.update_window()

    def on_go_to_album(self, action: Any, album_id: GLib.Variant):
        # Switch to the Alphabetical by Name view to guarantee that the album is there.
        self.app_config.state.current_album_search_query = AlbumSearchQuery(
            AlbumSearchQuery.Type.ALPHABETICAL_BY_NAME,
            genre=self.app_config.state.current_album_search_query.genre,
            year_range=self.app_config.state.current_album_search_query.year_range,
        )

        self.app_config.state.current_tab = "albums"
        self.app_config.state.selected_album_id = album_id.get_string()
        self.update_window()

    def on_go_to_artist(self, action: Any, artist_id: GLib.Variant):
        self.app_config.state.current_tab = "artists"
        self.app_config.state.selected_artist_id = artist_id.get_string()
        self.update_window()

    def browse_to(self, action: Any, item_id: GLib.Variant):
        self.app_config.state.current_tab = "browse"
        self.app_config.state.selected_browse_element_id = item_id.get_string()
        self.update_window()

    def on_go_to_playlist(self, action: Any, playlist_id: GLib.Variant):
        self.app_config.state.current_tab = "playlists"
        self.app_config.state.selected_playlist_id = playlist_id.get_string()
        self.update_window()

    def on_go_online(self, *args):
        self.on_refresh_window(None, {"__settings__": {"offline_mode": False}})

    def on_refresh_devices(self, *args):
        self.player_manager.refresh_players()

    def reset_state(self):
        if self.app_config.state.playing:
            self.on_play_pause()
        self.loading_state = True
        self.player_manager.reset()
        AdapterManager.reset(self.app_config, self.on_song_download_progress)
        self.loading_state = False

        # Update the window according to the new server configuration.
        self.update_window()

    def on_stack_change(self, stack: Gtk.Stack, _):
        self.app_config.state.current_tab = stack.get_visible_child_name()
        self.update_window()

    def on_song_clicked(
        self,
        win: Any,
        song_index: int,
        song_queue: Tuple[str, ...],
        metadata: Dict[str, Any],
    ):
        song_queue = tuple(song_queue)
        # Reset the play queue so that we don't ever revert back to the
        # previous one.
        old_play_queue = song_queue

        if (force_shuffle := metadata.get("force_shuffle_state")) is not None:
            self.app_config.state.shuffle_on = force_shuffle

        self.app_config.state.active_playlist_id = metadata.get("active_playlist_id")

        # If shuffle is enabled, then shuffle the playlist.
        if self.app_config.state.shuffle_on and not metadata.get("no_reshuffle"):
            song_id = song_queue[song_index]
            song_queue_list = list(
                song_queue[:song_index] + song_queue[song_index + 1 :]
            )
            random.shuffle(song_queue_list)
            song_queue = (song_id, *song_queue_list)
            song_index = 0

        self.play_song(
            song_index,
            reset=True,
            old_play_queue=old_play_queue,
            play_queue=song_queue,
        )

    def on_songs_removed(self, win: Any, song_indexes_to_remove: List[int]):
        self.app_config.state.play_queue = tuple(
            song_id
            for i, song_id in enumerate(self.app_config.state.play_queue)
            if i not in song_indexes_to_remove
        )

        # Determine how many songs before the currently playing one were also
        # deleted.
        before_current = [
            i
            for i in song_indexes_to_remove
            if i < self.app_config.state.current_song_index
        ]

        if self.app_config.state.current_song_index in song_indexes_to_remove:
            if len(self.app_config.state.play_queue) == 0:
                self.on_play_pause()
                self.app_config.state.current_song_index = -1
                self.update_window()
                return

            self.app_config.state.current_song_index -= len(before_current)
            self.play_song(self.app_config.state.current_song_index, reset=True)
        else:
            self.app_config.state.current_song_index -= len(before_current)
            self.update_window()
            self.save_play_queue()

    @dbus_propagate()
    def on_song_scrub(self, _, scrub_value: float):
        if not self.app_config.state.current_song or not self.window:
            return

        # This should not ever happen. The current_song should always have
        # a duration, but the Child object has `duration` optional because
        # it could be a directory.
        assert self.app_config.state.current_song.duration is not None
        new_time = self.app_config.state.current_song.duration * (scrub_value / 100)

        self.app_config.state.song_progress = new_time
        self.window.player_controls.update_scrubber(
            self.app_config.state.song_progress,
            self.app_config.state.current_song.duration,
            self.app_config.state.song_stream_cache_progress,
        )

        # If already playing, then make the player itself seek.
        if self.player_manager and self.player_manager.song_loaded:
            self.player_manager.seek(new_time)

        self.save_play_queue()

    def on_device_update(self, _, device_id: str):
        assert self.player_manager
        if device_id == self.app_config.state.current_device:
            return
        self.app_config.state.current_device = device_id

        if was_playing := self.app_config.state.playing:
            self.on_play_pause()

        self.player_manager.set_current_device_id(self.app_config.state.current_device)

        if self.dbus_manager:
            self.dbus_manager.property_diff()

        self.update_window()

        if was_playing:
            self.on_play_pause()
            if self.dbus_manager:
                self.dbus_manager.property_diff()

    @dbus_propagate()
    def on_mute_toggle(self, *args):
        self.app_config.state.is_muted = not self.app_config.state.is_muted
        self.player_manager.set_muted(self.app_config.state.is_muted)
        self.update_window()

    @dbus_propagate()
    def on_volume_change(self, _, value: float):
        assert self.player_manager
        self.app_config.state.volume = value
        self.player_manager.set_volume(self.app_config.state.volume)
        self.update_window()

    def on_window_key_press(self, window: Gtk.Window, event: Gdk.EventKey) -> bool:
        # Need to use bitwise & here to see if CTRL is pressed.
        if event.keyval == 102 and event.state & Gdk.ModifierType.CONTROL_MASK:
            # Ctrl + F
            window.search_entry.grab_focus()
            return False

        # Allow spaces to work in the text entry boxes.
        if (
            window.search_entry.has_focus()
            or window.playlists_panel.playlist_list.new_playlist_entry.has_focus()
        ):
            return False

        # Spacebar, home/prev
        keymap = {
            32: self.on_play_pause,
            65360: self.on_prev_track,
            65367: self.on_next_track,
        }

        action = keymap.get(event.keyval)
        if action:
            action()
            return True

        return False

    def on_song_download_progress(self, song_id: str, progress: DownloadProgress):
        assert self.window
        GLib.idle_add(self.window.update_song_download_progress, song_id, progress)

    def on_app_shutdown(self, app: "SublimeMusicApp"):
        self.exiting = True
        if glib_notify_exists:
            Notify.uninit()

        if tap_imported and self.tap:
            self.tap.stop()

        if self.app_config.provider is None:
            return

        if self.player_manager:
            if self.app_config.state.playing:
                self.save_play_queue()
            self.player_manager.pause()
            self.player_manager.shutdown()

        self.app_config.save()
        if self.dbus_manager:
            self.dbus_manager.shutdown()
        AdapterManager.shutdown()

    # ########## HELPER METHODS ########## #
    def show_configure_servers_dialog(
        self,
        provider_config: Optional[ProviderConfiguration] = None,
    ):
        """Show the Connect to Server dialog."""
        dialog = ConfigureProviderDialog(self.window, provider_config)
        result = dialog.run()
        if result == Gtk.ResponseType.APPLY:
            assert dialog.provider_config is not None
            provider_id = dialog.provider_config.id
            dialog.provider_config.persist_secrets()
            self.app_config.providers[provider_id] = dialog.provider_config
            self.app_config.save()

            if provider_id == self.app_config.current_provider_id:
                # Just update the window.
                self.update_window()
            else:
                # Switch to the new provider.
                if self.app_config.state.playing:
                    self.on_play_pause()
                self.app_config.current_provider_id = provider_id
                self.app_config.save()
                self.update_window(force=True)

        dialog.destroy()

    def update_window(self, force: bool = False):
        if not self.window:
            return
        logging.info(f"Updating window force={force}")
        GLib.idle_add(
            lambda: self.window.update(
                self.app_config, self.player_manager, force=force
            )
        )

    def update_play_state_from_server(self, prompt_confirm: bool = False):
        # TODO (#129): need to make the play queue list loading for the duration here if
        # prompt_confirm is False.
        if not prompt_confirm and self.app_config.state.playing:
            assert self.player_manager
            self.player_manager.pause()
            self.app_config.state.playing = False
            self.app_config.state.loading_play_queue = True
            self.update_window()

        def do_update(f: Result[PlayQueue]):
            play_queue = f.result()
            if not play_queue:
                self.app_config.state.loading_play_queue = False
                return
            play_queue.position = play_queue.position or timedelta(0)

            new_play_queue = tuple(s.id for s in play_queue.songs)
            new_song_progress = play_queue.position

            def do_resume(clear_notification: bool):
                assert self.player_manager
                if was_playing := self.app_config.state.playing:
                    self.on_play_pause()

                self.app_config.state.play_queue = new_play_queue
                self.app_config.state.song_progress = play_queue.position
                self.app_config.state.current_song_index = play_queue.current_index or 0
                self.app_config.state.loading_play_queue = False
                self.player_manager.reset()
                if clear_notification:
                    self.app_config.state.current_notification = None
                self.update_window()

                if was_playing:
                    self.on_play_pause()

            if prompt_confirm:
                # If there's not a significant enough difference in the song state,
                # don't prompt.
                progress_diff = 15.0
                if self.app_config.state.song_progress:
                    progress_diff = abs(
                        (
                            self.app_config.state.song_progress - new_song_progress
                        ).total_seconds()
                    )

                if (
                    self.app_config.state.play_queue == new_play_queue
                    and self.app_config.state.current_song
                ):
                    song_index = self.app_config.state.current_song_index
                    if song_index == play_queue.current_index and progress_diff < 15:
                        return

                # Show a notification to resume the play queue.
                resume_text = "Do you want to resume the play queue"
                if play_queue.changed_by or play_queue.changed:
                    resume_text += " saved"
                    if play_queue.changed_by:
                        resume_text += f" by {play_queue.changed_by}"
                    if play_queue.changed:
                        changed_str = play_queue.changed.astimezone(tz=None).strftime(
                            "%H:%M on %Y-%m-%d"
                        )
                        resume_text += f" at {changed_str}"
                resume_text += "?"

                self.app_config.state.current_notification = UIState.UINotification(
                    markup=f"<b>{resume_text}</b>",
                    actions=(("Resume", partial(do_resume, True)),),
                )
                self.update_window()

            else:  # just resume the play queue immediately
                do_resume(False)

        play_queue_future = AdapterManager.get_play_queue()
        play_queue_future.add_done_callback(lambda f: GLib.idle_add(do_update, f))

    song_playing_order_token = 0
    batch_download_jobs: Set[Result] = set()

    def play_song(
        self,
        song_index: int,
        reset: bool = False,
        old_play_queue: Tuple[str, ...] = None,
        play_queue: Tuple[str, ...] = None,
        playable_song_search_direction: int = 1,
    ):
        def do_reset():
            self.player_manager.reset()
            self.app_config.state.song_progress = timedelta(0)
            self.should_scrobble_song = True

        # Do this the old fashioned way so that we can have access to ``reset``
        # in the callback.
        @dbus_propagate(self)
        def do_play_song(order_token: int, song: Song):
            assert self.player_manager
            if order_token != self.song_playing_order_token:
                return

            uri = None
            try:
                if "file" in self.player_manager.supported_schemes:
                    uri = AdapterManager.get_song_file_uri(song)
            except CacheMissError:
                logging.debug("Couldn't find the file, will attempt to stream.")

            if not uri:
                try:
                    uri = AdapterManager.get_song_stream_uri(song)
                except Exception:
                    pass
                if (
                    not uri
                    or urlparse(uri).scheme not in self.player_manager.supported_schemes
                ):
                    self.app_config.state.current_notification = UIState.UINotification(
                        markup=f"<b>Unable to play {song.title}.</b>",
                        icon="dialog-error",
                    )
                    return

            # Prevent it from doing the thing where it continually loads
            # songs when it has to download.
            if reset:
                do_reset()

            # Start playing the song.
            if order_token != self.song_playing_order_token:
                return

            self.player_manager.play_media(
                uri,
                timedelta(0) if reset else self.app_config.state.song_progress,
                song,
            )
            self.app_config.state.playing = True
            self.update_window()

            # Show a song play notification.
            if self.app_config.song_play_notification:
                try:
                    if glib_notify_exists:
                        notification_lines = []
                        if album := song.album:
                            notification_lines.append(f"<i>{album.name}</i>")
                        if artist := song.artist:
                            notification_lines.append(artist.name)
                        song_notification = Notify.Notification.new(
                            song.title,
                            bleach.clean("\n".join(notification_lines)),
                        )
                        song_notification.add_action(
                            "clicked",
                            "Open Sublime Music",
                            lambda *a: self.window.present() if self.window else None,
                        )
                        song_notification.show()

                        def on_cover_art_download_complete(cover_art_filename: str):
                            if order_token != self.song_playing_order_token:
                                return

                            # Add the image to the notification, and re-show
                            # the notification.
                            song_notification.set_image_from_pixbuf(
                                GdkPixbuf.Pixbuf.new_from_file_at_scale(
                                    cover_art_filename, 70, 70, True
                                )
                            )
                            song_notification.show()

                        cover_art_result = AdapterManager.get_cover_art_uri(
                            song.cover_art, "file"
                        )
                        cover_art_result.add_done_callback(
                            lambda f: on_cover_art_download_complete(f.result())
                        )

                    if sys.platform == "darwin":
                        notification_lines = []
                        if album := song.album:
                            notification_lines.append(album.name)
                        if artist := song.artist:
                            notification_lines.append(artist.name)
                        notification_text = "\n".join(notification_lines)
                        osascript_command = [
                            "display",
                            "notification",
                            f'"{notification_text}"',
                            "with",
                            "title",
                            f'"{song.title}"',
                        ]

                        os.system(f"osascript -e '{' '.join(osascript_command)}'")
                except Exception:
                    logging.warning(
                        "Unable to display notification. Is a notification daemon running?"  # noqa: E501
                    )

            # Download current song and prefetch songs. Only do this if the adapter can
            # download songs and allow_song_downloads is True and download_on_stream is
            # True.
            def on_song_download_complete(song_id: str):
                if order_token != self.song_playing_order_token:
                    return

                # Hotswap to the downloaded song.
                if (
                    # TODO (#182) allow hotswap if not playing. This requires being able
                    # to replace the currently playing URI with something different.
                    self.app_config.state.playing
                    and self.app_config.state.current_song
                    and self.app_config.state.current_song.id == song_id
                ):
                    # Switch to the local media if the player can hotswap without lag.
                    # For example, MPV can is barely noticable whereas there's quite a
                    # delay with Chromecast.
                    assert self.player_manager
                    if self.player_manager.can_start_playing_with_no_latency:
                        self.player_manager.play_media(
                            AdapterManager.get_song_file_uri(song),
                            self.app_config.state.song_progress,
                            song,
                        )

                # Always update the window
                self.update_window()

            if (
                # This only makes sense if the adapter is networked.
                AdapterManager.ground_truth_adapter_is_networked()
                # Don't download in offline mode.
                and not self.app_config.offline_mode
                and self.app_config.allow_song_downloads
                and self.app_config.download_on_stream
                and AdapterManager.can_batch_download_songs()
            ):
                song_ids = [song.id]

                # Add the prefetch songs.
                if (
                    repeat_type := self.app_config.state.repeat_type
                ) != RepeatType.REPEAT_SONG:
                    song_idx = self.app_config.state.play_queue.index(song.id)
                    is_repeat_queue = RepeatType.REPEAT_QUEUE == repeat_type
                    prefetch_idxs = []
                    for i in range(self.app_config.prefetch_amount):
                        prefetch_idx: int = song_idx + 1 + i
                        play_queue_len: int = len(self.app_config.state.play_queue)
                        if is_repeat_queue or prefetch_idx < play_queue_len:
                            prefetch_idxs.append(
                                prefetch_idx % play_queue_len  # noqa: S001
                            )
                    song_ids.extend(
                        [self.app_config.state.play_queue[i] for i in prefetch_idxs]
                    )

                self.batch_download_jobs.add(
                    AdapterManager.batch_download_songs(
                        song_ids,
                        before_download=lambda _: self.update_window(),
                        on_song_download_complete=on_song_download_complete,
                        one_at_a_time=True,
                        delay=5,
                    )
                )

        if old_play_queue:
            self.app_config.state.old_play_queue = old_play_queue

        if play_queue:
            self.app_config.state.play_queue = play_queue

        self.app_config.state.current_song_index = song_index

        for job in self.batch_download_jobs:
            job.cancel()

        self.song_playing_order_token += 1

        if play_queue:
            GLib.timeout_add(
                5000,
                partial(
                    self.save_play_queue,
                    song_playing_order_token=self.song_playing_order_token,
                ),
            )

        # If in offline mode, go to the first song in the play queue after the given
        # song that is actually playable.
        if self.app_config.offline_mode:
            statuses = AdapterManager.get_cached_statuses(
                self.app_config.state.play_queue
            )
            playable_statuses = (
                SongCacheStatus.CACHED,
                SongCacheStatus.PERMANENTLY_CACHED,
            )
            can_play = False
            current_song_index = self.app_config.state.current_song_index

            if statuses[current_song_index] in playable_statuses:
                can_play = True
            elif self.app_config.state.repeat_type != RepeatType.REPEAT_SONG:
                # See if any other songs in the queue are playable.
                play_queue_len = len(self.app_config.state.play_queue)
                cursor = (
                    current_song_index + playable_song_search_direction
                ) % play_queue_len
                for _ in range(play_queue_len):  # Don't infinite loop.
                    if self.app_config.state.repeat_type == RepeatType.NO_REPEAT:
                        if (
                            playable_song_search_direction == 1
                            and cursor < current_song_index
                        ) or (
                            playable_song_search_direction == -1
                            and cursor > current_song_index
                        ):
                            # We wrapped around to the end of the play queue without
                            # finding a song that can be played, and we aren't allowed
                            # to loop back.
                            break

                    # If we find a playable song, stop and play it.
                    if statuses[cursor] in playable_statuses:
                        self.play_song(cursor, reset)
                        return

                    cursor = (cursor + playable_song_search_direction) % play_queue_len

            if not can_play:
                # There are no songs that can be played. Show a notification that you
                # have to go online to play anything and then don't go further.
                if was_playing := self.app_config.state.playing:
                    self.on_play_pause()

                def go_online_clicked():
                    self.app_config.state.current_notification = None
                    self.on_go_online()
                    if was_playing:
                        self.on_play_pause()

                if all(s == SongCacheStatus.NOT_CACHED for s in statuses):
                    markup = (
                        "<b>None of the songs in your play queue are cached for "
                        "offline playback.</b>\nGo online to start playing your queue."
                    )
                else:
                    markup = (
                        "<b>None of the remaining songs in your play queue are cached "
                        "for offline playback.</b>\nGo online to contiue playing your "
                        "queue."
                    )

                self.app_config.state.current_notification = UIState.UINotification(
                    icon="cloud-offline-symbolic",
                    markup=markup,
                    actions=(("Go Online", go_online_clicked),),
                )
                if reset:
                    do_reset()
                self.update_window()
                return

        song_details_future = AdapterManager.get_song_details(
            self.app_config.state.play_queue[self.app_config.state.current_song_index]
        )
        if song_details_future.data_is_available:
            song_details_future.add_done_callback(
                lambda f: do_play_song(self.song_playing_order_token, f.result())
            )
        else:
            song_details_future.add_done_callback(
                lambda f: GLib.idle_add(
                    partial(do_play_song, self.song_playing_order_token), f.result()
                ),
            )

    def save_play_queue(self, song_playing_order_token: int = None):
        if (
            len(self.app_config.state.play_queue) == 0
            or self.app_config.provider is None
            or (
                song_playing_order_token
                and song_playing_order_token != self.song_playing_order_token
            )
        ):
            return

        position = self.app_config.state.song_progress
        self.last_play_queue_update = position or timedelta(0)

        if AdapterManager.can_save_play_queue() and self.app_config.state.current_song:
            AdapterManager.save_play_queue(
                song_ids=self.app_config.state.play_queue,
                current_song_index=self.app_config.state.current_song_index,
                position=position,
            )
