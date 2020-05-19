import logging
import os
import random
import sys
from datetime import timedelta
from functools import partial
from pathlib import Path
from time import sleep
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

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

from .adapters import AdapterManager, AlbumSearchQuery, Result
from .adapters.api_objects import Playlist, PlayQueue, Song
from .config import AppConfiguration, ReplayGainType
from .dbus import dbus_propagate, DBusManager
from .players import ChromecastPlayer, MPVPlayer, Player, PlayerEvent
from .ui.configure_servers import ConfigureServersDialog
from .ui.main import MainWindow
from .ui.settings import SettingsDialog
from .ui.state import RepeatType, UIState


class SublimeMusicApp(Gtk.Application):
    def __init__(self, config_file: Path):
        super().__init__(application_id="com.sumnerevans.sublimemusic")
        if glib_notify_exists:
            Notify.init("Sublime Music")

        self.window: Optional[Gtk.Window] = None
        self.app_config = AppConfiguration.load_from_file(config_file)
        self.dbus_manager: Optional[DBusManager] = None

        self.connect("shutdown", self.on_app_shutdown)

    player: Player

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
        add_action("configure-servers", self.on_configure_servers)
        add_action("settings", self.on_settings)

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

        # Windows are associated with the application when the last one is
        # closed the application shuts down.
        self.window = MainWindow(application=self, title="Sublime Music")

        # Configure the CSS provider so that we can style elements on the
        # window.
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(
            os.path.join(os.path.dirname(__file__), "ui/app_styles.css")
        )
        context = Gtk.StyleContext()
        screen = Gdk.Screen.get_default()
        context.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

        self.window.stack.connect(
            "notify::visible-child", self.on_stack_change,
        )
        self.window.connect("song-clicked", self.on_song_clicked)
        self.window.connect("songs-removed", self.on_songs_removed)
        self.window.connect("refresh-window", self.on_refresh_window)
        self.window.connect("notification-closed", self.on_notification_closed)
        self.window.connect("go-to", self.on_window_go_to)
        self.window.connect("key-press-event", self.on_window_key_press)
        self.window.player_controls.connect("song-scrub", self.on_song_scrub)
        self.window.player_controls.connect("device-update", self.on_device_update)
        self.window.player_controls.connect("volume-change", self.on_volume_change)

        self.window.show_all()
        self.window.present()

        # Load the state for the server, if it exists.
        self.app_config.load_state()

        # If there is no current server, show the dialog to select a server.
        if self.app_config.server is None:
            self.show_configure_servers_dialog()

            # If they didn't add one with the dialog, close the window.
            if self.app_config.server is None:
                self.window.close()
                return

        # Configure the players
        self.last_play_queue_update = timedelta(0)
        self.loading_state = False
        self.should_scrobble_song = False

        def time_observer(value: Optional[float]):
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
            if event.type == PlayerEvent.Type.PLAY_STATE_CHANGE:
                assert event.playing
                self.app_config.state.playing = event.playing
                if self.dbus_manager:
                    self.dbus_manager.property_diff()
            elif event.type == PlayerEvent.Type.VOLUME_CHANGE:
                assert event.volume
                self.app_config.state.volume = event.volume
                if self.dbus_manager:
                    self.dbus_manager.property_diff()
            elif event.type == PlayerEvent.Type.STREAM_CACHE_PROGRESS_CHANGE:
                if (
                    self.loading_state
                    or not self.window
                    or not self.app_config.state.current_song
                    or not event.stream_cache_duration
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

            self.update_window()

        self.mpv_player = MPVPlayer(
            time_observer, on_track_end, on_player_event, self.app_config,
        )
        self.chromecast_player = ChromecastPlayer(
            time_observer, on_track_end, on_player_event, self.app_config,
        )
        self.player = self.mpv_player

        if self.app_config.state.current_device != "this device":
            # TODO (#120) attempt to connect to the previously connected device
            pass

        self.app_config.state.current_device = "this device"

        # Need to do this after we set the current device.
        self.player.volume = self.app_config.state.volume

        # Update after Adapter Initial Sync
        inital_sync_result = AdapterManager.initial_sync()
        inital_sync_result.add_done_callback(lambda _: self.update_window())

        # Prompt to load the play queue from the server.
        if self.app_config.server.sync_enabled:
            self.update_play_state_from_server(prompt_confirm=True)

        # Send out to the bus that we exist.
        if self.dbus_manager:
            self.dbus_manager.property_diff()

    # ########## DBUS MANAGMENT ########## #
    def do_dbus_register(self, connection: Gio.DBusConnection, path: str) -> bool:
        self.dbus_manager = DBusManager(
            connection,
            self.on_dbus_method_call,
            self.on_dbus_set_property,
            lambda: (self.app_config, self.player),
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
        second_microsecond_conversion = 1000000

        def seek_fn(offset: float):
            if not self.app_config.state.current_song:
                return
            offset_seconds = timedelta(seconds=offset / second_microsecond_conversion)
            new_seconds = self.app_config.state.song_progress + offset_seconds

            # This should not ever happen. The current_song should always have
            # a duration, but the Child object has `duration` optional because
            # it could be a directory.
            assert self.app_config.state.current_song.duration is not None
            self.on_song_scrub(
                None,
                (
                    new_seconds
                    / self.app_config.state.current_song.duration.total_seconds()
                )
                * 100,
            )

        def set_pos_fn(track_id: str, position: float = 0):
            if self.app_config.state.playing:
                self.on_play_pause()
            pos_seconds = timedelta(seconds=position / second_microsecond_conversion)
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
                    i, self.app_config.state.play_queue,
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
            index: int, max_count: int, order: str, reverse_order: bool,
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
                key=sorters.get(order, lambda p: p), reverse=reverse_order,
            )

            def make_playlist_tuple(p: Playlist) -> GLib.Variant:
                cover_art_filename = AdapterManager.get_cover_art_filename(
                    p.cover_art, allow_download=False,
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
    def on_refresh_window(
        self, _, state_updates: Dict[str, Any], force: bool = False,
    ):
        for k, v in state_updates.items():
            setattr(self.app_config.state, k, v)
        self.update_window(force=force)

    def on_notification_closed(self, _):
        self.app_config.state.current_notification = None
        self.update_window()

    def on_configure_servers(self, *args):
        self.show_configure_servers_dialog()

    def on_settings(self, *args):
        """Show the Settings dialog."""
        dialog = SettingsDialog(self.window, self.app_config)
        result = dialog.run()
        if result == Gtk.ResponseType.OK:
            self.app_config.port_number = int(dialog.data["port_number"].get_text())
            self.app_config.always_stream = dialog.data["always_stream"].get_active()
            self.app_config.download_on_stream = dialog.data[
                "download_on_stream"
            ].get_active()
            self.app_config.song_play_notification = dialog.data[
                "song_play_notification"
            ].get_active()
            self.app_config.serve_over_lan = dialog.data["serve_over_lan"].get_active()
            self.app_config.prefetch_amount = dialog.data[
                "prefetch_amount"
            ].get_value_as_int()
            self.app_config.concurrent_download_limit = dialog.data[
                "concurrent_download_limit"
            ].get_value_as_int()
            self.app_config.replay_gain = ReplayGainType.from_string(
                dialog.data["replay_gain"].get_active_id()
            )
            self.app_config.save()
            self.reset_state()
        dialog.destroy()

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

        if self.player.song_loaded:
            self.player.toggle_play()
            self.save_play_queue()
        else:
            # This is from a restart, start playing the file.
            self.play_song(self.app_config.state.current_song_index)

        self.app_config.state.playing = not self.app_config.state.playing
        self.update_window()

    def on_next_track(self, *args):
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

        self.play_song(song_index_to_play, reset=True)

    def on_prev_track(self, *args):
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

        self.play_song(song_index_to_play, reset=True)

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
        self.update_window(force=True)

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

    def on_server_list_changed(self, action: Any, servers: GLib.Variant):
        self.app_config.servers = servers
        self.app_config.save()

    def on_connected_server_changed(
        self, action: Any, current_server_index: int,
    ):
        if self.app_config.server:
            self.app_config.save()
        self.app_config.current_server_index = current_server_index
        self.app_config.save()

        self.reset_state()

    def reset_state(self):
        if self.app_config.state.playing:
            self.on_play_pause()
        self.loading_state = True
        self.player.reset()
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
            self.play_song(
                self.app_config.state.current_song_index, reset=True,
            )
        else:
            self.app_config.state.current_song_index -= len(before_current)
            self.update_window()
            self.save_play_queue()

    @dbus_propagate()
    def on_song_scrub(self, win: Any, scrub_value: float):
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
        if self.player.song_loaded:
            self.player.seek(new_time)

        self.save_play_queue()

    def on_device_update(self, win: Any, device_uuid: str):
        if device_uuid == self.app_config.state.current_device:
            return
        self.app_config.state.current_device = device_uuid

        was_playing = self.app_config.state.playing
        self.player.pause()
        self.player._song_loaded = False
        self.app_config.state.playing = False

        if self.dbus_manager:
            self.dbus_manager.property_diff()

        self.update_window()

        if device_uuid == "this device":
            self.player = self.mpv_player
        else:
            self.chromecast_player.set_playing_chromecast(device_uuid)
            self.player = self.chromecast_player

        if was_playing:
            self.on_play_pause()
            if self.dbus_manager:
                self.dbus_manager.property_diff()

    @dbus_propagate()
    def on_mute_toggle(self, *args):
        self.app_config.state.is_muted = not self.app_config.state.is_muted
        self.player.is_muted = self.app_config.state.is_muted
        self.update_window()

    @dbus_propagate()
    def on_volume_change(self, _, value: float):
        self.app_config.state.volume = value
        self.player.volume = self.app_config.state.volume
        self.update_window()

    def on_window_key_press(self, window: Gtk.Window, event: Gdk.EventKey,) -> bool:
        # Need to use bitwise & here to see if CTRL is pressed.
        if event.keyval == 102 and event.state & Gdk.ModifierType.CONTROL_MASK:
            # Ctrl + F
            window.search_entry.grab_focus()
            return False

        if window.search_entry.has_focus():
            return False

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

    def on_app_shutdown(self, app: "SublimeMusicApp"):
        if glib_notify_exists:
            Notify.uninit()

        if tap_imported and self.tap:
            self.tap.stop()

        if self.app_config.server is None:
            return

        self.player.pause()
        self.chromecast_player.shutdown()
        self.mpv_player.shutdown()

        self.app_config.save()
        self.save_play_queue()
        if self.dbus_manager:
            self.dbus_manager.shutdown()
        AdapterManager.shutdown()

    # ########## HELPER METHODS ########## #
    def show_configure_servers_dialog(self):
        """Show the Connect to Server dialog."""
        dialog = ConfigureServersDialog(self.window, self.app_config)
        dialog.connect("server-list-changed", self.on_server_list_changed)
        dialog.connect("connected-server-changed", self.on_connected_server_changed)
        dialog.run()
        dialog.destroy()

    def update_window(self, force: bool = False):
        if not self.window:
            return
        logging.info(f"Updating window force={force}")
        GLib.idle_add(lambda: self.window.update(self.app_config, force=force))

    def update_play_state_from_server(self, prompt_confirm: bool = False):
        # TODO (#129): need to make the play queue list loading for the duration here if
        # prompt_confirm is False.
        if not prompt_confirm and self.app_config.state.playing:
            assert self.player
            self.player.pause()
            self.app_config.state.playing = False
            self.update_window()

        def do_update(f: Result[PlayQueue]):
            play_queue = f.result()
            play_queue.position = play_queue.position or timedelta(0)

            new_play_queue = tuple(s.id for s in play_queue.songs)
            new_song_progress = play_queue.position

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

                # TODO (#167): info bar here (maybe pop up above the player controls?)
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

                def on_resume_click():
                    if was_playing := self.app_config.state.playing:
                        self.on_play_pause()

                    self.app_config.state.play_queue = new_play_queue
                    self.app_config.state.song_progress = play_queue.position
                    self.app_config.state.current_song_index = (
                        play_queue.current_index or 0
                    )
                    self.player.reset()
                    self.app_config.state.current_notification = None
                    self.update_window()

                    if was_playing:
                        self.on_play_pause()

                self.app_config.state.current_notification = UIState.UINotification(
                    markup=f"<b>{resume_text}</b>",
                    actions=(("Resume", on_resume_click),),
                )
                self.update_window()

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
    ):
        # Do this the old fashioned way so that we can have access to ``reset``
        # in the callback.
        @dbus_propagate(self)
        def do_play_song(order_token: int, song: Song):
            if order_token != self.song_playing_order_token:
                return

            uri = AdapterManager.get_song_filename_or_stream(
                song, force_stream=self.app_config.always_stream,
            )

            # Prevent it from doing the thing where it continually loads
            # songs when it has to download.
            if reset:
                self.player.reset()
                self.app_config.state.song_progress = timedelta(0)
                self.should_scrobble_song = True

            # Start playing the song.
            if order_token != self.song_playing_order_token:
                return

            self.player.play_media(
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
                            song.title, "\n".join(notification_lines),
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

                        cover_art_result = AdapterManager.get_cover_art_filename(
                            song.cover_art
                        )
                        cover_art_result.add_done_callback(
                            lambda f: on_cover_art_download_complete(f.result())
                        )

                    if sys.platform == "darwin":
                        notification_lines = []
                        if song.album:
                            notification_lines.append(song.album)
                        if song.artist:
                            notification_lines.append(song.artist)
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
                    logging.exception(
                        "Unable to display notification. Is a notification daemon running?"  # noqa: E501
                    )

            # Download current song and prefetch songs. Only do this if
            # download_on_stream is True and always_stream is off.
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
                    assert self.player
                    if self.player.can_hotswap_source:
                        self.player.play_media(
                            AdapterManager.get_song_filename_or_stream(song),
                            self.app_config.state.song_progress,
                            song,
                        )

                # Always update the window
                self.update_window()

            if (
                self.app_config.download_on_stream
                and not self.app_config.always_stream
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

            def save_play_queue_later(order_token: int):
                sleep(5)
                if order_token != self.song_playing_order_token:
                    return
                self.save_play_queue()

            Result(partial(save_play_queue_later, self.song_playing_order_token))

        song_details_future = AdapterManager.get_song_details(
            self.app_config.state.play_queue[self.app_config.state.current_song_index]
        )
        song_details_future.add_done_callback(
            lambda f: GLib.idle_add(
                partial(do_play_song, self.song_playing_order_token), f.result()
            ),
        )

    def save_play_queue(self):
        # TODO let this be delayed as well
        if len(self.app_config.state.play_queue) == 0:
            return

        position = self.app_config.state.song_progress
        self.last_play_queue_update = position or timedelta(0)

        if self.app_config.server.sync_enabled and self.app_config.state.current_song:
            AdapterManager.save_play_queue(
                song_ids=self.app_config.state.play_queue,
                current_song_index=self.app_config.state.current_song_index,
                position=position,
            )
