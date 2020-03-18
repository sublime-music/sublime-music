import logging
import math
import os
import random
from concurrent.futures import Future
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Notify

from .cache_manager import CacheManager
from .config import ReplayGainType
from .dbus_manager import dbus_propagate, DBusManager
from .players import ChromecastPlayer, MPVPlayer, PlayerEvent
from .server.api_objects import Child, Directory, Playlist
from .state_manager import ApplicationState, RepeatType
from .ui.configure_servers import ConfigureServersDialog
from .ui.main import MainWindow
from .ui.settings import SettingsDialog


class SublimeMusicApp(Gtk.Application):
    def __init__(self, config_file: str):
        super().__init__(application_id="com.sumnerevans.sublimemusic")
        Notify.init('Sublime Music')

        self.window: Optional[Gtk.Window] = None
        self.state = ApplicationState()
        self.state.config_file = config_file

        self.connect('shutdown', self.on_app_shutdown)

    def do_startup(self):
        Gtk.Application.do_startup(self)

        def add_action(name: str, fn: Callable, parameter_type: str = None):
            """Registers an action with the application."""
            if type(parameter_type) == str:
                parameter_type = GLib.VariantType(parameter_type)
            action = Gio.SimpleAction.new(name, parameter_type)
            action.connect('activate', fn)
            self.add_action(action)

        # Add action for menu items.
        add_action('configure-servers', self.on_configure_servers)
        add_action('settings', self.on_settings)

        # Add actions for player controls
        add_action('play-pause', self.on_play_pause)
        add_action('next-track', self.on_next_track)
        add_action('prev-track', self.on_prev_track)
        add_action('repeat-press', self.on_repeat_press)
        add_action('shuffle-press', self.on_shuffle_press)

        # Navigation actions.
        add_action('play-next', self.on_play_next, parameter_type='as')
        add_action('add-to-queue', self.on_add_to_queue, parameter_type='as')
        add_action('go-to-album', self.on_go_to_album, parameter_type='s')
        add_action('go-to-artist', self.on_go_to_artist, parameter_type='s')
        add_action('browse-to', self.browse_to, parameter_type='s')
        add_action(
            'go-to-playlist', self.on_go_to_playlist, parameter_type='s')

        add_action('mute-toggle', self.on_mute_toggle)
        add_action(
            'update-play-queue-from-server',
            lambda a, p: self.update_play_state_from_server(),
        )

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
            os.path.join(os.path.dirname(__file__), 'ui/app_styles.css'))
        context = Gtk.StyleContext()
        screen = Gdk.Screen.get_default()
        context.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        self.window.stack.connect(
            'notify::visible-child',
            self.on_stack_change,
        )
        self.window.connect('song-clicked', self.on_song_clicked)
        self.window.connect('songs-removed', self.on_songs_removed)
        self.window.connect('refresh-window', self.on_refresh_window)
        self.window.connect('go-to', self.on_window_go_to)
        self.window.connect('key-press-event', self.on_window_key_press)
        self.window.player_controls.connect('song-scrub', self.on_song_scrub)
        self.window.player_controls.connect(
            'device-update', self.on_device_update)
        self.window.player_controls.connect(
            'volume-change', self.on_volume_change)

        self.window.show_all()
        self.window.present()

        # Load the configuration and update the UI with the curent server, if
        # it exists.
        self.state.load()

        # If there is no current server, show the dialog to select a server.
        if self.state.config.server is None:
            self.show_configure_servers_dialog()

            # If they didn't add one with the dialog, close the window.
            if self.state.config.server is None:
                self.window.close()
                return

        self.update_window()

        # Configure the players
        self.last_play_queue_update = 0
        self.loading_state = False
        self.should_scrobble_song = False

        def time_observer(value: Optional[float]):
            if (self.loading_state or not self.window
                    or not self.state.current_song):
                return

            if value is None:
                self.last_play_queue_update = 0
                return

            self.state.song_progress = value
            GLib.idle_add(
                self.window.player_controls.update_scrubber,
                self.state.song_progress,
                self.state.current_song.duration,
            )

            if self.last_play_queue_update + 15 <= value:
                self.save_play_queue()

            if value > 5 and self.should_scrobble_song:
                CacheManager.scrobble(self.state.current_song.id)
                self.should_scrobble_song = False

        def on_track_end():
            if (self.state.current_song_index == len(self.state.play_queue) - 1
                    and self.state.repeat_type == RepeatType.NO_REPEAT):
                self.state.playing = False
                self.state.current_song_index = -1
                GLib.idle_add(self.update_window)
                return

            GLib.idle_add(self.on_next_track)

        @dbus_propagate(self)
        def on_player_event(event: PlayerEvent):
            if event.name == 'play_state_change':
                self.state.playing = event.value
            elif event.name == 'volume_change':
                self.state.volume = event.value

            GLib.idle_add(self.update_window)

        self.mpv_player = MPVPlayer(
            time_observer,
            on_track_end,
            on_player_event,
            self.state.config,
        )
        self.chromecast_player = ChromecastPlayer(
            time_observer,
            on_track_end,
            on_player_event,
            self.state.config,
        )
        self.player = self.mpv_player

        if self.state.current_device != 'this device':
            # TODO (#120)
            pass

        self.state.current_device = 'this device'

        # Need to do this after we set the current device.
        self.player.volume = self.state.volume

        # Prompt to load the play queue from the server.
        if self.state.config.server.sync_enabled:
            self.update_play_state_from_server(prompt_confirm=True)

        # Send out to the bus that we exist.
        self.dbus_manager.property_diff()

    # ########## DBUS MANAGMENT ########## #
    def do_dbus_register(
            self, connection: Gio.DBusConnection, path: str) -> bool:
        self.dbus_manager = DBusManager(
            connection,
            self.on_dbus_method_call,
            self.on_dbus_set_property,
            lambda: (self.state, getattr(self, 'player', None)),
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
            if not self.state.current_song:
                return
            offset_seconds = offset / second_microsecond_conversion
            new_seconds = self.state.song_progress + offset_seconds
            self.on_song_scrub(
                None, new_seconds / self.state.current_song.duration * 100)

        def set_pos_fn(track_id: str, position: float = 0):
            if self.state.playing:
                self.on_play_pause()
            pos_seconds = position / second_microsecond_conversion
            self.state.song_progress = pos_seconds
            track_id, occurrence = track_id.split('/')[-2:]

            # Find the (N-1)th time that the track id shows up in the list. (N
            # is the -*** suffix on the track id.)
            song_index = [
                i for i, x in enumerate(self.state.play_queue) if x == track_id
            ][int(occurrence) or 0]

            self.play_song(song_index)

        def get_tracks_metadata(track_ids: List[str]) -> GLib.Variant:
            if len(track_ids):
                # We are lucky, just return an empty list.
                return GLib.Variant('(aa{sv})', ([], ))

            # Have to calculate all of the metadatas so that we can deal with
            # repeat song IDs.
            metadatas: Iterable[Any] = [
                self.dbus_manager.get_mpris_metadata(i, self.state.play_queue)
                for i in range(len(self.state.play_queue))
            ]

            # Get rid of all of the tracks that were not requested.
            metadatas = filter(
                lambda m: m['mpris:trackid'] in track_ids, metadatas)

            # Sort them so they get returned in the same order as they were
            # requested.
            metadatas = sorted(
                metadatas, key=lambda m: track_ids.index(m['mpris:trackid']))

            # Turn them into dictionaries that can actually be serialized into
            # a GLib.Variant.
            metadatas = map(
                lambda m: {k: DBusManager.to_variant(v)
                           for k, v in m.items()},
                metadatas,
            )

            return GLib.Variant('(aa{sv})', (list(metadatas), ))

        def activate_playlist(playlist_id: str):
            playlist_id = playlist_id.split('/')[-1]
            playlist = CacheManager.get_playlist(playlist_id).result()

            # Calculate the song id to play.
            song_idx = 0
            if self.state.shuffle_on:
                song_idx = random.randint(0, len(playlist.entry) - 1)

            self.on_song_clicked(
                None,
                song_idx,
                [s.id for s in playlist.entry],
                {'active_playlist_id': playlist_id},
            )

        def get_playlists(
                index: int,
                max_count: int,
                order: str,
                reverse_order: bool,
        ) -> GLib.Variant:
            playlists_result = CacheManager.get_playlists()
            if playlists_result.is_future:
                # We don't want to wait for the response in this case, so just
                # return an empty array.
                return GLib.Variant('(a(oss))', ([], ))

            playlists = playlists_result.result()

            sorters = {
                'Alphabetical': lambda p: p.name,
                'Created': lambda p: p.created,
                'Modified': lambda p: p.changed,
            }
            playlists.sort(
                key=sorters.get(order, lambda p: p),
                reverse=reverse_order,
            )

            def make_playlist_tuple(p: Playlist) -> GLib.Variant:
                cover_art_filename = CacheManager.get_cover_art_filename(
                    p.coverArt,
                    allow_download=False,
                ).result()
                return (f'/playlist/{p.id}', p.name, cover_art_filename or '')

            return GLib.Variant(
                '(a(oss))', (
                    [
                        make_playlist_tuple(p)
                        for p in playlists[index:(index + max_count)]
                    ], ))

        method_call_map: Dict[str, Dict[str, Any]] = {
            'org.mpris.MediaPlayer2': {
                'Raise': self.window and self.window.present,
                'Quit': self.window and self.window.destroy,
            },
            'org.mpris.MediaPlayer2.Player': {
                'Next': self.on_next_track,
                'Previous': self.on_prev_track,
                'Pause': self.state.playing and self.on_play_pause,
                'PlayPause': self.on_play_pause,
                'Stop': self.state.playing and self.on_play_pause,
                'Play': not self.state.playing and self.on_play_pause,
                'Seek': seek_fn,
                'SetPosition': set_pos_fn,
            },
            'org.mpris.MediaPlayer2.TrackList': {
                'GoTo': set_pos_fn,
                'GetTracksMetadata': get_tracks_metadata,
            },
            'org.mpris.MediaPlayer2.Playlists': {
                'ActivatePlaylist': activate_playlist,
                'GetPlaylists': get_playlists,
            },
        }
        method_fn = method_call_map.get(interface, {}).get(method)
        if method_fn is None:
            logging.warning(
                f'Unknown/unimplemented method: {interface}.{method}.')
        invocation.return_value(
            method_fn(*params) if callable(method_fn) else None)

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
            self.state.repeat_type = RepeatType.from_mpris_loop_status(
                new_loop_status.get_string())
            self.update_window()

        def set_shuffle(new_val: GLib.Variant):
            if new_val.get_boolean() != self.state.shuffle_on:
                self.on_shuffle_press(None, None)

        def set_volume(new_val: GLib.Variant):
            self.on_volume_change(None, new_val.get_double() * 100)

        setter_map: Dict[str, Dict[str, Any]] = {
            'org.mpris.MediaPlayer2.Player': {
                'LoopStatus': change_loop,
                'Rate': lambda _: None,
                'Shuffle': set_shuffle,
                'Volume': set_volume,
            }
        }

        setter = setter_map.get(interface, {}).get(property_name)
        if setter is None:
            logging.warning('Set: Unknown property: {property_name}.')
            return
        if callable(setter):
            setter(value)

    # ########## ACTION HANDLERS ########## #
    @dbus_propagate()
    def on_refresh_window(
        self,
        _: Any,
        state_updates: Dict[str, Any],
        force: bool = False,
    ):
        for k, v in state_updates.items():
            setattr(self.state, k, v)
        self.update_window(force=force)

    def on_configure_servers(self, *args):
        self.show_configure_servers_dialog()

    def on_settings(self, *args):
        """Show the Settings dialog."""
        dialog = SettingsDialog(self.window, self.state.config)
        result = dialog.run()
        if result == Gtk.ResponseType.OK:
            self.state.config.port_number = int(
                dialog.data['port_number'].get_text())
            self.state.config.always_stream = dialog.data[
                'always_stream'].get_active()
            self.state.config.download_on_stream = dialog.data[
                'download_on_stream'].get_active()
            self.state.config.song_play_notification = dialog.data[
                'song_play_notification'].get_active()
            self.state.config.serve_over_lan = dialog.data[
                'serve_over_lan'].get_active()
            self.state.config.prefetch_amount = dialog.data[
                'prefetch_amount'].get_value_as_int()
            self.state.config.concurrent_download_limit = dialog.data[
                'concurrent_download_limit'].get_value_as_int()
            self.state.config.replay_gain = ReplayGainType.from_string(
                dialog.data['replay_gain'].get_active_id())
            self.state.save_config()
            self.reset_state()
        dialog.destroy()

    def on_window_go_to(self, win: Any, action: str, value: str):
        {
            'album': self.on_go_to_album,
            'artist': self.on_go_to_artist,
            'playlist': self.on_go_to_playlist,
        }[action](None, GLib.Variant('s', value))

    @dbus_propagate()
    def on_play_pause(self, *args):
        if self.state.current_song_index < 0:
            return

        if self.player.song_loaded:
            self.player.toggle_play()
            self.save_play_queue()
        else:
            # This is from a restart, start playing the file.
            self.play_song(self.state.current_song_index)

        self.state.playing = not self.state.playing
        self.update_window()

    def on_next_track(self, *args):
        # Handle song repeating
        if self.state.repeat_type == RepeatType.REPEAT_SONG:
            song_index_to_play = self.state.current_song_index
        # Wrap around the play queue if at the end.
        elif self.state.current_song_index == len(self.state.play_queue) - 1:
            # This may happen due to D-Bus.
            if self.state.repeat_type == RepeatType.NO_REPEAT:
                return
            song_index_to_play = 0
        else:
            song_index_to_play = self.state.current_song_index + 1

        self.play_song(song_index_to_play, reset=True)

    def on_prev_track(self, *args):
        # Go back to the beginning of the song if we are past 5 seconds.
        # Otherwise, go to the previous song.
        if self.state.repeat_type == RepeatType.REPEAT_SONG:
            song_index_to_play = self.state.current_song_index
        elif self.state.song_progress < 5:
            if (self.state.current_song_index == 0
                    and self.state.repeat_type == RepeatType.NO_REPEAT):
                song_index_to_play = 0
            else:
                song_index_to_play = (self.state.current_song_index - 1) % len(
                    self.state.play_queue)
        else:
            song_index_to_play = self.state.current_song_index

        self.play_song(song_index_to_play, reset=True)

    @dbus_propagate()
    def on_repeat_press(self, *args):
        # Cycle through the repeat types.
        new_repeat_type = RepeatType((self.state.repeat_type.value + 1) % 3)
        self.state.repeat_type = new_repeat_type
        self.update_window()

    @dbus_propagate()
    def on_shuffle_press(self, *args):
        if self.state.shuffle_on:
            # Revert to the old play queue.
            self.state.current_song_index = self.state.old_play_queue.index(
                self.state.current_song.id)
            self.state.play_queue = self.state.old_play_queue.copy()
        else:
            self.state.old_play_queue = self.state.play_queue.copy()

            # Remove the current song, then shuffle and put the song back.
            song_id = self.state.current_song.id
            del self.state.play_queue[self.state.current_song_index]
            random.shuffle(self.state.play_queue)
            self.state.play_queue = [song_id] + self.state.play_queue
            self.state.current_song_index = 0

        self.state.shuffle_on = not self.state.shuffle_on
        self.update_window()

    @dbus_propagate()
    def on_play_next(self, action: Any, song_ids: List[str]):
        if self.state.current_song is None:
            insert_at = 0
        else:
            insert_at = self.state.current_song_index + 1

        self.state.play_queue = (
            self.state.play_queue[:insert_at] + list(song_ids)
            + self.state.play_queue[insert_at:])
        self.state.old_play_queue.extend(song_ids)
        self.update_window()

    @dbus_propagate()
    def on_add_to_queue(self, action: Any, song_ids: GLib.Variant):
        self.state.play_queue.extend(song_ids)
        self.state.old_play_queue.extend(song_ids)
        self.update_window()

    def on_go_to_album(self, action: Any, album_id: GLib.Variant):
        # Switch to the By Year view (or genre, if year is not available) to
        # guarantee that the album is there.
        album = CacheManager.get_album(album_id.get_string()).result()
        if isinstance(album, Directory):
            if len(album.child) > 0:
                album = album.child[0]

        if album.get('year'):
            self.state.current_album_sort = 'byYear'
            self.state.current_album_from_year = album.year
            self.state.current_album_to_year = album.year
        elif album.get('genre'):
            self.state.current_album_sort = 'byGenre'
            self.state.current_album_genre = album.genre
        else:
            dialog = Gtk.MessageDialog(
                transient_for=self.window,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text='Could not go to album',
            )
            dialog.format_secondary_markup(
                'Could not go to the album because it does not have a year or '
                'genre.')
            dialog.run()
            dialog.destroy()
            return

        self.state.current_tab = 'albums'
        self.state.selected_album_id = album_id.get_string()
        self.update_window(force=True)

    def on_go_to_artist(self, action: Any, artist_id: GLib.Variant):
        self.state.current_tab = 'artists'
        self.state.selected_artist_id = artist_id.get_string()
        self.update_window()

    def browse_to(self, action: Any, item_id: GLib.Variant):
        self.state.current_tab = 'browse'
        self.state.selected_browse_element_id = item_id.get_string()
        self.update_window()

    def on_go_to_playlist(self, action: Any, playlist_id: GLib.Variant):
        self.state.current_tab = 'playlists'
        self.state.selected_playlist_id = playlist_id.get_string()
        self.update_window()

    def on_server_list_changed(self, action: Any, servers: GLib.Variant):
        self.state.config.servers = servers
        self.state.save_config()

    def on_connected_server_changed(
        self,
        action: Any,
        current_server: GLib.Variant,
    ):
        if self.state.config.server:
            self.state.save()
        self.state.config.current_server = current_server
        self.state.save_config()

        self.reset_state()

    def reset_state(self):
        if self.state.playing:
            self.on_play_pause()
        self.loading_state = True
        self.state.load()
        self.player.reset()
        self.loading_state = False

        # Update the window according to the new server configuration.
        self.update_window()

    def on_stack_change(self, stack: Gtk.Stack, _: Any):
        self.state.current_tab = stack.get_visible_child_name()
        self.update_window()

    def on_song_clicked(
        self,
        win: Any,
        song_index: int,
        song_queue: List[str],
        metadata: Dict[str, Any],
    ):
        # Reset the play queue so that we don't ever revert back to the
        # previous one.
        old_play_queue = song_queue.copy()

        if metadata.get('force_shuffle_state') is not None:
            self.state.shuffle_on = metadata['force_shuffle_state']

        if metadata.get('active_playlist_id') is not None:
            self.state.active_playlist_id = metadata.get('active_playlist_id')
        else:
            self.state.active_playlist_id = None

        # If shuffle is enabled, then shuffle the playlist.
        if self.state.shuffle_on and not metadata.get('no_reshuffle'):
            song_id = song_queue[song_index]

            del song_queue[song_index]
            random.shuffle(song_queue)
            song_queue = [song_id] + song_queue
            song_index = 0

        self.play_song(
            song_index,
            reset=True,
            old_play_queue=old_play_queue,
            play_queue=song_queue,
        )

    def on_songs_removed(self, win: Any, song_indexes_to_remove: List[int]):
        self.state.play_queue = [
            song_id for i, song_id in enumerate(self.state.play_queue)
            if i not in song_indexes_to_remove
        ]

        # Determine how many songs before the currently playing one were also
        # deleted.
        before_current = [
            i for i in song_indexes_to_remove
            if i < self.state.current_song_index
        ]

        if self.state.current_song_index in song_indexes_to_remove:
            if len(self.state.play_queue) == 0:
                self.on_play_pause()
                self.state.current_song_index = -1
                self.update_window()
                return

            self.state.current_song_index -= len(before_current)
            self.play_song(self.state.current_song_index, reset=True)
        else:
            self.state.current_song_index -= len(before_current)
            self.update_window()
            self.save_play_queue()

    @dbus_propagate()
    def on_song_scrub(self, win: Any, scrub_value: float):
        if not self.state.current_song or not self.window:
            return

        new_time = self.state.current_song.duration * (scrub_value / 100)

        self.state.song_progress = new_time
        self.window.player_controls.update_scrubber(
            self.state.song_progress, self.state.current_song.duration)

        # If already playing, then make the player itself seek.
        if self.player.song_loaded:
            self.player.seek(new_time)

        self.save_play_queue()

    def on_device_update(self, win: Any, device_uuid: str):
        if device_uuid == self.state.current_device:
            return
        self.state.current_device = device_uuid

        was_playing = self.state.playing
        self.player.pause()
        self.player._song_loaded = False
        self.state.playing = False

        self.dbus_manager.property_diff()
        self.update_window()

        if device_uuid == 'this device':
            self.player = self.mpv_player
        else:
            self.chromecast_player.set_playing_chromecast(device_uuid)
            self.player = self.chromecast_player

        if was_playing:
            self.on_play_pause()
            self.dbus_manager.property_diff()

    @dbus_propagate()
    def on_mute_toggle(self, *args):
        self.state.is_muted = not self.state.is_muted
        self.player.is_muted = self.state.is_muted
        self.update_window()

    @dbus_propagate()
    def on_volume_change(self, _: Any, value: float):
        self.state.volume = value
        self.player.volume = self.state.volume
        self.update_window()

    def on_window_key_press(
            self,
            window: Gtk.Window,
            event: Gdk.EventKey,
    ) -> bool:
        # Need to use bitwise & here to see if CTRL is pressed.
        if (event.keyval == 102
                and event.state & Gdk.ModifierType.CONTROL_MASK):
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

    def on_app_shutdown(self, app: 'SublimeMusicApp'):
        Notify.uninit()

        if self.state.config.server is None:
            return

        self.player.pause()
        self.chromecast_player.shutdown()
        self.mpv_player.shutdown()

        self.state.save()
        self.save_play_queue()
        self.dbus_manager.shutdown()
        CacheManager.shutdown()

    # ########## HELPER METHODS ########## #
    def show_configure_servers_dialog(self):
        """Show the Connect to Server dialog."""
        dialog = ConfigureServersDialog(self.window, self.state.config)
        dialog.connect('server-list-changed', self.on_server_list_changed)
        dialog.connect(
            'connected-server-changed', self.on_connected_server_changed)
        dialog.run()
        dialog.destroy()

    def update_window(self, force: bool = False):
        if not self.window:
            return
        GLib.idle_add(lambda: self.window.update(self.state, force=force))

    def update_play_state_from_server(self, prompt_confirm: bool = False):
        # TODO (#129): need to make the up next list loading for the duration
        # here if prompt_confirm is False.
        was_playing = self.state.playing
        self.player.pause()
        self.state.playing = False
        self.update_window()

        def do_update(f: Future):
            play_queue = f.result()
            new_play_queue = [s.id for s in play_queue.entry]
            new_current_song_id = str(play_queue.current)
            new_song_progress = play_queue.position / 1000

            if prompt_confirm:
                # If there's not a significant enough difference, don't prompt.
                progress_diff = 15
                if self.state.song_progress:
                    progress_diff = abs(
                        self.state.song_progress - new_song_progress)

                if (self.state.play_queue == new_play_queue
                        and self.state.current_song
                        and self.state.current_song.id == new_current_song_id
                        and progress_diff < 15):
                    return

                dialog = Gtk.MessageDialog(
                    transient_for=self.window,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.YES_NO,
                    text='Resume Playback?',
                )

                dialog.format_secondary_markup(
                    'Do you want to resume the play queue saved by '
                    + str(play_queue.changedBy) + ' at '
                    + play_queue.changed.astimezone(
                        tz=None).strftime('%H:%M on %Y-%m-%d') + '?')
                result = dialog.run()
                dialog.destroy()
                if result != Gtk.ResponseType.YES:
                    return

            self.state.play_queue = new_play_queue
            self.state.song_progress = play_queue.position / 1000

            self.state.current_song_index = self.state.play_queue.index(
                new_current_song_id)

            self.player.reset()
            self.update_window()

            if was_playing:
                self.on_play_pause()

        play_queue_future = CacheManager.get_play_queue()
        play_queue_future.add_done_callback(
            lambda f: GLib.idle_add(do_update, f))

    song_playing_order_token = 0

    def play_song(
        self,
        song_index: int,
        reset: bool = False,
        old_play_queue: List[str] = None,
        play_queue: List[str] = None,
    ):
        # Do this the old fashioned way so that we can have access to ``reset``
        # in the callback.
        @dbus_propagate(self)
        def do_play_song(song: Child):
            uri, stream = CacheManager.get_song_filename_or_stream(
                song,
                force_stream=self.state.config.always_stream,
            )
            # Prevent it from doing the thing where it continually loads
            # songs when it has to download.
            if reset:
                self.player.reset()
                self.state.song_progress = 0
                self.should_scrobble_song = True

            # Show a song play notification.
            if self.state.config.song_play_notification:
                try:
                    notification_lines = []
                    if song.album:
                        notification_lines.append(f'<i>{song.album}</i>')
                    if song.artist:
                        notification_lines.append(song.artist)
                    song_notification = Notify.Notification.new(
                        song.title,
                        '\n'.join(notification_lines),
                    )
                    song_notification.add_action(
                        'clicked',
                        'Open Sublime Music',
                        lambda *a: self.window.present()
                        if self.window else None,
                    )
                    song_notification.show()

                    def on_cover_art_download_complete(
                        cover_art_filename: str,
                        order_token: int,
                    ):
                        if order_token != self.song_playing_order_token:
                            return

                        # Add the image to the notification, and re-show the
                        # notification.
                        song_notification.set_image_from_pixbuf(
                            GdkPixbuf.Pixbuf.new_from_file_at_scale(
                                cover_art_filename, 70, 70, True))
                        song_notification.show()

                    def get_cover_art_filename(
                            order_token: int) -> Tuple[str, int]:
                        return (
                            CacheManager.get_cover_art_filename(
                                song.coverArt).result(),
                            order_token,
                        )

                    self.song_playing_order_token += 1
                    cover_art_future = CacheManager.create_future(
                        get_cover_art_filename,
                        self.song_playing_order_token,
                    )
                    cover_art_future.add_done_callback(
                        lambda f: on_cover_art_download_complete(*f.result()))
                except Exception:
                    logging.warning(
                        'Unable to display notification. Is a notification '
                        'daemon running?')

            def on_song_download_complete(song_id: int):
                if (self.state.current_song
                        and self.state.current_song.id != song.id):
                    return

                # Switch to the local media if the player can hotswap (MPV can,
                # Chromecast cannot hotswap without lag).
                if self.player.can_hotswap_source:
                    self.player.play_media(
                        CacheManager.get_song_filename_or_stream(song)[0],
                        self.state.song_progress,
                        song,
                    )
                GLib.idle_add(self.update_window)

            # If streaming, also download the song, unless configured not to,
            # or configured to always stream.
            if (stream and self.state.config.download_on_stream
                    and not self.state.config.always_stream):
                CacheManager.batch_download_songs(
                    [song.id],
                    before_download=lambda: self.update_window(),
                    on_song_download_complete=on_song_download_complete,
                )

            self.player.play_media(uri, self.state.song_progress, song)
            self.state.playing = True
            self.update_window()

            # Prefetch songs
            if self.state.repeat_type != RepeatType.REPEAT_SONG:
                song_idx = self.state.play_queue.index(song.id)
                prefetch_idxs = []
                for i in range(self.state.config.prefetch_amount):
                    prefetch_idx: int = song_idx + 1 + i
                    play_queue_len: int = len(self.state.play_queue)
                    if (self.state.repeat_type == RepeatType.REPEAT_QUEUE
                            or prefetch_idx < play_queue_len):
                        prefetch_idxs.append(
                            prefetch_idx % play_queue_len)  # noqa: S001
                CacheManager.batch_download_songs(
                    [self.state.play_queue[i] for i in prefetch_idxs],
                    before_download=lambda: GLib.idle_add(self.update_window),
                    on_song_download_complete=lambda _: GLib.idle_add(
                        self.update_window),
                )

        if old_play_queue:
            self.state.old_play_queue = old_play_queue

        if play_queue:
            self.state.play_queue = play_queue

        self.state.current_song_index = song_index

        if play_queue:
            self.save_play_queue()

        song_details_future = CacheManager.get_song_details(
            self.state.play_queue[self.state.current_song_index])
        song_details_future.add_done_callback(
            lambda f: GLib.idle_add(do_play_song, f.result()), )

    def save_play_queue(self):
        if len(self.state.play_queue) == 0:
            return

        position = self.state.song_progress
        self.last_play_queue_update = position or 0

        if self.state.config.server.sync_enabled and self.state.current_song:
            CacheManager.save_play_queue(
                play_queue=self.state.play_queue,
                current=self.state.current_song.id,
                position=math.floor(position * 1000) if position else None,
            )
