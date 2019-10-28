import os
import re
import math
import random

from os import environ
import concurrent.futures

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import Gdk, Gio, GLib, Gtk, Notify, GdkPixbuf

from .ui.main import MainWindow
from .ui.configure_servers import ConfigureServersDialog
from .ui.settings import SettingsDialog

from .dbus_manager import DBusManager, dbus_propagate
from .state_manager import ApplicationState, RepeatType
from .cache_manager import CacheManager
from .server.api_objects import Child
from .ui.common.players import PlayerEvent, MPVPlayer, ChromecastPlayer


class SublimeMusicApp(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="com.sumnerevans.sublimemusic",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            **kwargs,
        )
        Notify.init('Sublime Music')

        self.window = None
        self.state = ApplicationState()

        # Specify Command Line Options
        self.add_main_option(
            'config',
            ord('c'),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.FILENAME,
            'Specify a configuration file. Defaults to '
            '~/.config/sublime-music/config.json',
            None,
        )

        self.connect('shutdown', self.on_app_shutdown)

    # Handle command line option parsing.
    def do_command_line(self, command_line):
        options = command_line.get_options_dict()

        # Config File
        config_file = options.lookup_value('config')
        if config_file:
            config_file = config_file.get_bytestring().decode('utf-8')
        else:
            # Default to ~/.config/sublime-music.
            config_folder = (
                environ.get('XDG_CONFIG_HOME') or environ.get('APPDATA')
                or os.path.join(environ.get('HOME'), '.config'))
            config_folder = os.path.join(config_folder, 'sublime-music')
            config_file = os.path.join(config_folder, 'config.json')

        self.state.config_file = config_file

        # Have to do this or else the application doesn't work. Not entirely
        # sure why, but C-bindings...
        self.activate()
        return 0

    def do_startup(self):
        Gtk.Application.do_startup(self)

        def add_action(name: str, fn, parameter_type=None):
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
        add_action(
            'play-queue-click', self.on_play_queue_click, parameter_type='s')

        # Navigation actions.
        add_action('play-next', self.on_play_next, parameter_type='as')
        add_action('add-to-queue', self.on_add_to_queue, parameter_type='as')
        add_action('go-to-album', self.on_go_to_album, parameter_type='s')
        add_action('go-to-artist', self.on_go_to_artist, parameter_type='s')
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
        self.window.connect('refresh-window', self.on_refresh_window)
        self.window.player_controls.connect('song-scrub', self.on_song_scrub)
        self.window.player_controls.connect(
            'device-update', self.on_device_update)
        self.window.player_controls.connect(
            'volume-change', self.on_volume_change)
        self.window.connect('key-press-event', self.on_window_key_press)

        self.window.show_all()
        self.window.present()

        # Load the configuration and update the UI with the curent server, if
        # it exists.
        self.state.load()

        # If there is no current server, show the dialog to select a server.
        if (self.state.config.current_server is None
                or self.state.config.current_server < 0):
            self.show_configure_servers_dialog()
            if self.current_server is None:
                self.window.close()
                return

        self.update_window()

        # Configure the players
        self.last_play_queue_update = 0

        def time_observer(value):
            self.state.song_progress = value
            GLib.idle_add(
                self.window.player_controls.update_scrubber,
                self.state.song_progress,
                self.state.current_song.duration,
            )
            if not value:
                self.last_play_queue_update = 0
            elif self.last_play_queue_update + 15 <= value:
                self.save_play_queue()

        def on_track_end():
            current_idx = self.state.play_queue.index(
                self.state.current_song.id)

            if (current_idx == len(self.state.play_queue) - 1
                    and self.state.repeat_type == RepeatType.NO_REPEAT):
                self.state.playing = False
                self.state.current_song = None
                GLib.idle_add(self.update_window)
                return

            GLib.idle_add(self.on_next_track)

        @dbus_propagate(self)
        def on_player_event(event: PlayerEvent):
            if event.name == 'play_state_change':
                self.state.playing = event.value
            elif event.name == 'volume_change':
                self.state.old_volume = self.state.volume
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

        self.player.volume = self.state.volume

        if self.state.current_device != 'this device':
            # TODO figure out how to activate the chromecast if possible
            # without blocking the main thread. Also, need to make it obvious
            # that we are trying to connect.
            pass

        self.state.current_device = 'this device'

        # Prompt to load the play queue from the server.
        # TODO should this be behind sync enabled?
        if self.current_server.sync_enabled:
            self.update_play_state_from_server(prompt_confirm=True)

        # Send out to the bus that we exist.
        self.dbus_manager.property_diff()

    # ########## DBUS MANAGMENT ########## #
    def do_dbus_register(self, connection, path):
        def get_state_and_player():
            return (self.state, getattr(self, 'player', None))

        self.dbus_manager = DBusManager(
            connection,
            self.on_dbus_method_call,
            self.on_dbus_set_property,
            get_state_and_player,
        )
        return True

    def on_dbus_method_call(
            self,
            connection,
            sender,
            path,
            interface,
            method,
            params,
            invocation,
    ):
        second_microsecond_conversion = 1000000
        track_id_re = re.compile(r'/song/(.*)')
        playlist_id_re = re.compile(r'/playlist/(.*)')

        def seek_fn(offset):
            offset_seconds = offset / second_microsecond_conversion
            new_seconds = self.state.song_progress + offset_seconds
            self.on_song_scrub(
                None, new_seconds / self.state.current_song.duration * 100)

        def set_pos_fn(track_id, position=0):
            if self.state.playing:
                self.on_play_pause()
            pos_seconds = position / second_microsecond_conversion
            self.state.song_progress = pos_seconds
            self.play_song(track_id_re.match(track_id).group(1))

        def get_track_metadata(track_ids):
            metadatas = []

            song_details_futures = [
                CacheManager.get_song_details(track_id) for track_id in (
                    track_id_re.match(tid).group(1) for tid in track_ids)
            ]
            for f in concurrent.futures.wait(song_details_futures).done:
                metadata = self.dbus_manager.get_mpris_metadata(f.result())
                metadatas.append(
                    {
                        k: DBusManager.to_variant(v)
                        for k, v in metadata.items()
                    })

            return GLib.Variant('(aa{sv})', (metadatas, ))

        def activate_playlist(playlist_id):
            playlist_id = playlist_id_re.match(playlist_id).group(1)
            playlist = CacheManager.get_playlist(playlist_id).result()

            # Calculate the song id to play.
            song_id = playlist.entry[0].id
            if self.state.shuffle_on:
                rand_idx = random.randint(0, len(playlist.entry) - 1)
                song_id = playlist.entry[rand_idx].id

            self.on_song_clicked(
                None,
                song_id,
                [s.id for s in playlist.entry],
                {'active_playlist_id': playlist_id},
            )

        def get_playlists(index, max_count, order, reverse_order):
            playlists = CacheManager.get_playlists().result()
            sorters = {
                'Alphabetical': lambda p: p.name,
                'Created': lambda p: p.created,
                'Modified': lambda p: p.changed,
            }
            playlists.sort(
                key=sorters.get(order, lambda p: p),
                reverse=reverse_order,
            )

            return GLib.Variant(
                '(a(oss))', (
                    [
                        (
                            '/playlist/' + p.id,
                            p.name,
                            CacheManager.get_cover_art_filename(
                                p.coverArt,
                                allow_download=False,
                            ).result() or '',
                        )
                        for p in playlists[index:(index + max_count)]
                        if p.songCount > 0
                    ], ))

        method_call_map = {
            'org.mpris.MediaPlayer2': {
                'Raise': self.window.present,
                'Quit': self.window.destroy,
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
                'GetTracksMetadata': get_track_metadata,
            },
            'org.mpris.MediaPlayer2.Playlists': {
                'ActivatePlaylist': activate_playlist,
                'GetPlaylists': get_playlists,
            },
        }
        method = method_call_map.get(interface, {}).get(method)
        if method is None:
            print(f'Unknown/unimplemented method: {interface}.{method}')
        invocation.return_value(method(*params) if callable(method) else None)

    def on_dbus_set_property(
            self,
            connection,
            sender,
            path,
            interface,
            property_name,
            value,
    ):
        def change_loop(new_loop_status):
            self.state.repeat_type = RepeatType.from_mpris_loop_status(
                new_loop_status.get_string())
            self.update_window()

        def set_shuffle(new_val):
            if new_val.get_boolean() != self.state.shuffle_on:
                self.on_shuffle_press(None, None)

        def set_volume(new_val):
            self.on_volume_change(None, value.get_double() * 100)

        setter_map = {
            'org.mpris.MediaPlayer2.Player': {
                'LoopStatus': change_loop,
                'Rate': lambda _: None,
                'Shuffle': set_shuffle,
                'Volume': set_volume,
            }
        }

        setter = setter_map.get(interface).get(property_name)
        if setter is None:
            print('Set: Unknown property:', setter)
            return
        if callable(setter):
            setter(value)

    # ########## ACTION HANDLERS ########## #
    @dbus_propagate()
    def on_refresh_window(self, _, state_updates, force=False):
        for k, v in state_updates.items():
            setattr(self.state, k, v)
        self.update_window(force=force)

    def on_configure_servers(self, action, param):
        self.show_configure_servers_dialog()

    def on_settings(self, action, param):
        """Show the Settings dialog."""
        dialog = SettingsDialog(self.window, self.state.config)
        result = dialog.run()
        if result == Gtk.ResponseType.OK:
            self.state.config.show_headers = dialog.data[
                'show_headers'].get_active()
            self.state.config.always_stream = dialog.data[
                'always_stream'].get_active()
            self.state.config.download_on_stream = dialog.data[
                'download_on_stream'].get_active()
            self.state.config.song_play_notification = dialog.data[
                'song_play_notification'].get_active()
            self.state.config.prefetch_amount = dialog.data[
                'prefetch_amount'].get_value_as_int()
            self.state.config.concurrent_download_limit = dialog.data[
                'concurrent_download_limit'].get_value_as_int()
            self.state.save()
            self.reset_cache_manager()
        dialog.destroy()

    @dbus_propagate()
    def on_play_pause(self, *args):
        if self.state.current_song is None:
            return

        if self.player.song_loaded:
            self.player.toggle_play()
            self.save_play_queue()
        else:
            # This is from a restart, start playing the file.
            self.play_song(self.state.current_song.id)

        self.state.playing = not self.state.playing
        self.update_window()

    def on_next_track(self, *args):
        current_idx = self.state.play_queue.index(self.state.current_song.id)

        # Handle song repeating
        if self.state.repeat_type == RepeatType.REPEAT_SONG:
            current_idx = current_idx - 1
        # Wrap around the play queue if at the end.
        elif current_idx == len(self.state.play_queue) - 1:
            # This may happen due to D-Bus.
            if self.state.repeat_type == RepeatType.NO_REPEAT:
                return
            current_idx = -1

        self.play_song(self.state.play_queue[current_idx + 1], reset=True)

    def on_prev_track(self, *args):
        # TODO there is a bug where you can't go back multiple songs fast
        current_idx = self.state.play_queue.index(self.state.current_song.id)
        # Go back to the beginning of the song if we are past 5 seconds.
        # Otherwise, go to the previous song.
        if self.state.repeat_type == RepeatType.REPEAT_SONG:
            song_to_play = current_idx
        elif self.state.song_progress < 5:
            if (current_idx == 0
                    and self.state.repeat_type == RepeatType.NO_REPEAT):
                song_to_play = 0
            else:
                song_to_play = current_idx - 1
        else:
            song_to_play = current_idx

        self.play_song(self.state.play_queue[song_to_play], reset=True)

    @dbus_propagate()
    def on_repeat_press(self, action, params):
        # Cycle through the repeat types.
        new_repeat_type = RepeatType((self.state.repeat_type.value + 1) % 3)
        self.state.repeat_type = new_repeat_type
        self.update_window()

    @dbus_propagate()
    def on_shuffle_press(self, action, params):
        if self.state.shuffle_on:
            # Revert to the old play queue.
            self.state.play_queue = self.state.old_play_queue
        else:
            self.state.old_play_queue = self.state.play_queue.copy()

            # Remove the current song, then shuffle and put the song back.
            song_id = self.state.current_song.id
            self.state.play_queue.remove(song_id)
            random.shuffle(self.state.play_queue)
            self.state.play_queue = [song_id] + self.state.play_queue

        self.state.shuffle_on = not self.state.shuffle_on
        self.update_window()

    def on_play_queue_click(self, action, song_id):
        self.play_song(song_id.get_string(), reset=True)

    @dbus_propagate()
    def on_play_next(self, action, song_ids):
        if self.state.current_song is None:
            insert_at = 0
        else:
            insert_at = (
                self.state.play_queue.index(self.state.current_song.id) + 1)

        self.state.play_queue = (
            self.state.play_queue[:insert_at] + list(song_ids)
            + self.state.play_queue[insert_at:])
        self.state.old_play_queue.extend(song_ids)
        self.update_window()

    @dbus_propagate()
    def on_add_to_queue(self, action, song_ids):
        self.state.play_queue.extend(song_ids)
        self.state.old_play_queue.extend(song_ids)
        self.update_window()

    def on_go_to_album(self, action, album_id):
        # TODO
        self.state.current_tab = 'albums'
        self.update_window()

    def on_go_to_artist(self, action, artist_id):
        self.state.current_tab = 'artists'
        self.state.selected_artist_id = artist_id.get_string()
        self.update_window()

    def on_go_to_playlist(self, action, playlist_id):
        self.state.current_tab = 'playlists'
        self.state.selected_playlist_id = playlist_id.get_string()
        self.update_window()

    def on_server_list_changed(self, action, servers):
        self.state.config.servers = servers
        self.state.save()

    def on_connected_server_changed(self, action, current_server):
        self.state.config.current_server = current_server
        self.state.save()

        self.reset_cache_manager()
        self.update_window()

    def reset_cache_manager(self):
        CacheManager.reset(
            self.state.config,
            self.current_server
            if self.state.config.current_server >= 0 else None,
        )

        # Update the window according to the new server configuration.
        self.update_window()

    def on_stack_change(self, stack, child):
        self.state.current_tab = stack.get_visible_child_name()
        self.update_window()

    def on_song_clicked(self, win, song_id, song_queue, metadata):
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
        if self.state.shuffle_on:
            song_queue.remove(song_id)
            random.shuffle(song_queue)
            song_queue = [song_id] + song_queue

        self.play_song(
            song_id,
            reset=True,
            old_play_queue=old_play_queue,
            play_queue=song_queue,
        )

    @dbus_propagate()
    def on_song_scrub(self, _, scrub_value):
        if not hasattr(self.state, 'current_song'):
            return

        new_time = self.state.current_song.duration * (scrub_value / 100)

        self.state.song_progress = new_time
        self.window.player_controls.update_scrubber(
            self.state.song_progress, self.state.current_song.duration)

        # If already playing, then make the player itself seek.
        if self.player.song_loaded:
            self.player.seek(new_time)

        self.save_play_queue()

    def on_device_update(self, _, device_uuid):
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
    def on_mute_toggle(self, action, _):
        self.state.is_muted = not self.state.is_muted
        self.player.is_muted = self.state.is_muted
        self.update_window()

    @dbus_propagate()
    def on_volume_change(self, _, value):
        self.state.volume = value
        self.player.volume = self.state.volume
        self.update_window()

    def on_window_key_press(self, window, event):
        keymap = {
            32: self.on_play_pause,
            65360: self.on_prev_track,
            65367: self.on_next_track,
        }

        action = keymap.get(event.keyval)
        if action:
            action()
            return True

    def on_app_shutdown(self, app):
        Notify.uninit()

        if self.current_server is None:
            return

        self.player.pause()
        self.chromecast_player.shutdown()
        self.mpv_player.shutdown()

        self.state.save()
        self.save_play_queue()
        self.dbus_manager.shutdown()
        CacheManager.shutdown()

    # ########## PROPERTIES ########## #
    @property
    def current_server(self):
        if len(self.state.config.servers) < 1:
            return None
        return self.state.config.servers[self.state.config.current_server]

    # ########## HELPER METHODS ########## #
    def show_configure_servers_dialog(self):
        """Show the Connect to Server dialog."""
        dialog = ConfigureServersDialog(self.window, self.state.config)
        dialog.connect('server-list-changed', self.on_server_list_changed)
        dialog.connect(
            'connected-server-changed', self.on_connected_server_changed)
        dialog.run()
        dialog.destroy()

    def update_window(self, force=False):
        GLib.idle_add(lambda: self.window.update(self.state, force=force))

    def update_play_state_from_server(self, prompt_confirm=False):
        # TODO need to make the up next list loading for the duration here
        was_playing = self.state.playing
        self.player.pause()
        self.state.playing = False
        self.update_window()

        def do_update(f):
            play_queue = f.result()
            new_play_queue = [s.id for s in play_queue.entry]
            new_current_song_id = str(play_queue.current)
            new_song_progress = play_queue.position / 1000

            if prompt_confirm:
                # If there's not a significant enough difference, don't prompt.
                if (self.state.play_queue == new_play_queue
                        and self.state.current_song
                        and self.state.current_song.id == new_current_song_id
                        and abs(self.state.song_progress - new_song_progress) <
                        15):
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

            current_song_idx = self.state.play_queue.index(new_current_song_id)
            self.state.current_song = play_queue.entry[current_song_idx]

            self.player.reset()
            self.update_window()

            if was_playing:
                self.on_play_pause()

        play_queue_future = CacheManager.get_play_queue()
        play_queue_future.add_done_callback(
            lambda f: GLib.idle_add(do_update, f))

    def play_song(
            self,
            song_id: str,
            reset=False,
            old_play_queue=None,
            play_queue=None,
    ):
        # Do this the old fashioned way so that we can have access to ``reset``
        # in the callback.
        @dbus_propagate(self)
        def do_play_song(song: Child):
            uri, stream = CacheManager.get_song_filename_or_stream(
                song,
                force_stream=self.state.config.always_stream,
            )

            self.state.current_song = song
            self.state.playing = True
            self.update_window()

            # Show a song play notification.
            if self.state.config.song_play_notification:

                # TODO someone needs to test this, Dunst doesn't seem to
                # support it.
                def on_notification_click(*args):
                    self.window.present()

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
                        on_notification_click,
                    )
                    song_notification.show()

                    def on_cover_art_download_complete(cover_art_filename):
                        # Add the image to the notification, and re-draw the
                        # notification.
                        song_notification.set_image_from_pixbuf(
                            GdkPixbuf.Pixbuf.new_from_file(cover_art_filename))
                        song_notification.show()

                    cover_art_future = CacheManager.get_cover_art_filename(
                        song.coverArt, size=70)
                    cover_art_future.add_done_callback(
                        lambda f: on_cover_art_download_complete(f.result()))
                except:
                    print(
                        'Unable to display notification.',
                        'Is a notification daemon running?',
                    )

            # Prevent it from doing the thing where it continually loads
            # songs when it has to download.
            if reset:
                self.player.reset()
                self.state.song_progress = 0

            def on_song_download_complete(song_id):
                if self.state.current_song != song.id:
                    return

                # Switch to the local media if the player can hotswap (MPV can,
                # Chromecast cannot hotswap without lag).
                if self.player.can_hotswap_source:
                    downloaded_filename = (
                        CacheManager.get_song_filename_or_stream(song)[0])
                    self.player.play_media(
                        downloaded_filename, self.state.song_progress, song)
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

            if old_play_queue:
                self.state.old_play_queue = old_play_queue

            if play_queue:
                self.state.play_queue = play_queue
                self.save_play_queue()

            # Prefetch songs
            if self.state.repeat_type != RepeatType.REPEAT_SONG:
                song_idx = self.state.play_queue.index(song.id)
                prefetch_idxs = []
                for i in range(self.state.config.prefetch_amount):
                    prefetch_idx = song_idx + 1 + i
                    play_queue_len = len(self.state.play_queue)
                    if (prefetch_idx < play_queue_len or
                            self.state.repeat_type == RepeatType.REPEAT_QUEUE):
                        prefetch_idxs.append(prefetch_idx % play_queue_len)
                CacheManager.batch_download_songs(
                    [self.state.play_queue[i] for i in prefetch_idxs],
                    before_download=lambda: GLib.idle_add(self.update_window),
                    on_song_download_complete=lambda _: GLib.idle_add(
                        self.update_window),
                )

            if self.current_server.sync_enabled:
                CacheManager.scrobble(song.id)

        song_details_future = CacheManager.get_song_details(song_id)
        song_details_future.add_done_callback(
            lambda f: GLib.idle_add(do_play_song, f.result()), )

    def save_play_queue(self):
        if len(self.state.play_queue) == 0:
            return

        position = self.state.song_progress
        self.last_play_queue_update = position

        if self.current_server.sync_enabled and self.state.current_song:
            CacheManager.save_play_queue(
                play_queue=self.state.play_queue,
                current=self.state.current_song.id,
                position=math.floor(position * 1000) if position else None,
            )
