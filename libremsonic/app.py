import os
import math
import random

import mpv

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, Gio, GLib, Gtk

from .ui.main import MainWindow
from .ui.configure_servers import ConfigureServersDialog

from .state_manager import ApplicationState, RepeatType
from .cache_manager import CacheManager
from .server.api_objects import Child


class LibremsonicApp(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="com.sumnerevans.libremsonic",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            **kwargs,
        )
        self.window = None
        self.state = ApplicationState()

        # Specify Command Line Options
        self.add_main_option(
            'config', ord('c'), GLib.OptionFlags.NONE, GLib.OptionArg.FILENAME,
            'Specify a configuration file. Defaults to ~/.config/libremsonic/config.json',
            None)

        self.connect('shutdown', self.on_app_shutdown)

        self.player = mpv.MPV()

        self.last_play_queue_update = 0

        # Need to do this for determining if we are at the end of the song.
        # It's dumb, but whatever.
        self.had_progress_value = False

        @self.player.property_observer('time-pos')
        def time_observer(_name, value):
            self.state.song_progress = value
            GLib.idle_add(
                self.window.player_controls.update_scrubber,
                self.state.song_progress,
                self.state.current_song.duration,
            )
            if value is None and self.had_progress_value:
                GLib.idle_add(self.on_next_track, None, None)
                self.had_progress_value = False

            if not value:
                self.last_play_queue_update = 0
            elif self.last_play_queue_update + 15 <= value:
                self.save_play_queue()
                self.had_progress_value = True

    # Handle command line option parsing.
    def do_command_line(self, command_line):
        options = command_line.get_options_dict()

        # Config File
        config_file = options.lookup_value('config')
        if config_file:
            config_file = config_file.get_bytestring().decode('utf-8')
        else:
            # Default to ~/.config/libremsonic.
            config_folder = (os.environ.get('XDG_CONFIG_HOME')
                             or os.path.expanduser('~/.config'))
            config_folder = os.path.join(config_folder, 'libremsonic')
            config_file = os.path.join(config_folder, 'config.yaml')

        self.state.config_file = config_file

        # Have to do this or else the application doesn't work. Not entirely
        # sure why, but C-bindings...
        self.activate()
        return 0

    def do_startup(self):
        Gtk.Application.do_startup(self)

        def add_action(name: str, fn):
            """Registers an action with the application."""
            action = Gio.SimpleAction.new(name, None)
            action.connect('activate', fn)
            self.add_action(action)

        # Add action for menu items.
        add_action('configure-servers', self.on_configure_servers)

        # Add actions for player controls
        add_action('play-pause', self.on_play_pause)
        add_action('next-track', self.on_next_track)
        add_action('prev-track', self.on_prev_track)
        add_action('repeat-press', self.on_repeat_press)
        add_action('shuffle-press', self.on_shuffle_press)

        add_action('mute-toggle', self.on_mute_toggle)
        add_action(
            'update-play-queue-from-server',
            lambda a, p: self.update_play_state_from_server(),
        )

    def do_activate(self):
        # We only allow a single window and raise any existing ones
        if not self.window:
            # Windows are associated with the application when the last one is
            # closed the application shuts down.
            self.window = MainWindow(application=self, title="LibremSonic")

            # Configure the CSS provider so that we can style elements on the
            # window.
            css_provider = Gtk.CssProvider()
            css_provider.load_from_path(
                os.path.join(os.path.dirname(__file__), 'ui/app_styles.css'))
            context = Gtk.StyleContext()
            screen = Gdk.Screen.get_default()
            context.add_provider_for_screen(screen, css_provider,
                                            Gtk.STYLE_PROVIDER_PRIORITY_USER)

        self.window.stack.connect('notify::visible-child',
                                  self.on_stack_change)
        self.window.connect('song-clicked', self.on_song_clicked)
        self.window.player_controls.connect('song-scrub', self.on_song_scrub)
        self.window.player_controls.volume_slider.connect(
            'value-changed', self.on_volume_change)
        self.window.connect('key-press-event', self.on_window_key_press)

        # Display the window.
        self.window.show_all()
        self.window.present()

        # Load the configuration and update the UI with the curent server, if
        # it exists.
        self.state.load()

        # If there is no current server, show the dialog to select a server.
        if (self.state.config.current_server is None
                or self.state.config.current_server < 0):
            self.show_configure_servers_dialog()

    # ########## ACTION HANDLERS ########## #
    def on_configure_servers(self, action, param):
        self.show_configure_servers_dialog()

    def on_play_pause(self, action=None, param=None):
        if self.player.time_pos is None:
            # This is from a restart, start playing the file.
            self.play_song(self.state.current_song.id)
        else:
            self.player.cycle('pause')
            self.save_play_queue()

        self.state.playing = not self.state.playing
        self.update_window()

    def on_next_track(self, action, params):
        current_idx = self.state.play_queue.index(self.state.current_song.id)

        # Handle song repeating
        if self.state.repeat_type == RepeatType.REPEAT_SONG:
            current_idx = current_idx - 1
        # Wrap around the play queue if at the end.
        elif current_idx == len(self.state.play_queue) - 1:
            current_idx = -1

        self.play_song(self.state.play_queue[current_idx + 1], reset=True)

    def on_prev_track(self, action, params):
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

    def on_repeat_press(self, action, params):
        # Cycle through the repeat types.
        new_repeat_type = RepeatType((self.state.repeat_type.value + 1) % 3)
        self.state.repeat_type = new_repeat_type
        self.update_window()

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

    def on_server_list_changed(self, action, servers):
        self.state.config.servers = servers
        self.state.save()

    def on_connected_server_changed(self, action, current_server):
        self.state.config.current_server = current_server
        self.state.save()

        # Reset the CacheManager.
        CacheManager.reset(
            self.state.config,
            self.state.config.servers[current_server]
            if current_server >= 0 else None,
        )

        # Update the window according to the new server configuration.
        self.update_window()

    def on_stack_change(self, stack, child):
        self.update_window()

    def on_song_clicked(self, win, song_id, song_queue):
        # Need to reset this here to prevent it from going to the next song.
        self.had_progress_value = False

        # Reset the play queue so that we don't ever revert back to the
        # previous one.
        old_play_queue = song_queue.copy()

        # If shuffle is enabled, then shuffle the playlist.
        # TODO refactor to make a function.
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

    def on_song_scrub(self, _, scrub_value):
        if not hasattr(self.state, 'current_song'):
            return

        new_time = self.state.current_song.duration * (scrub_value / 100)

        if not self.player.time_pos:
            # This is from a restart. Just change the song_progress and when
            # they click play it will seek to that location.
            self.state.song_progress = new_time
            self.window.player_controls.update_scrubber(
                self.state.song_progress, self.state.current_song.duration)
        else:
            self.player.seek(str(new_time), 'absolute')

        self.save_play_queue()

    def on_mute_toggle(self, action, _):
        if self.state.volume == 0:
            new_volume = self.state.old_volume
        else:
            self.state.old_volume = self.state.volume
            new_volume = 0

        self.state.volume = new_volume
        self.player.volume = new_volume
        self.update_window()

    def on_volume_change(self, scale):
        self.state.volume = scale.get_value()
        self.player.volume = self.state.volume
        self.update_window()

    def on_window_key_press(self, window, event):
        # Returning True prevents further propagation of the event.
        if event.keyval == 32:
            self.on_play_pause()
            return True

    def on_app_shutdown(self, app):
        self.player.pause = True
        self.state.save()
        self.save_play_queue()

    # ########## HELPER METHODS ########## #
    def show_configure_servers_dialog(self):
        """Show the Connect to Server dialog."""
        dialog = ConfigureServersDialog(self.window, self.state.config)
        dialog.connect('server-list-changed', self.on_server_list_changed)
        dialog.connect('connected-server-changed',
                       self.on_connected_server_changed)
        dialog.run()
        dialog.destroy()

    def update_window(self):
        GLib.idle_add(self.window.update, self.state)

    def update_play_state_from_server(self):
        # TODO make this non-blocking eventually (need to make everything in
        # loading state)
        play_queue = CacheManager.get_play_queue()
        self.state.play_queue = [s.id for s in play_queue.entry]
        self.state.song_progress = play_queue.position / 1000

        current_song_idx = self.state.play_queue.index(str(play_queue.current))
        self.state.current_song = play_queue.entry[current_song_idx]

        self.update_window()

    def play_song(
            self,
            song: Child,
            reset=False,
            old_play_queue=None,
            play_queue=None,
    ):
        # Do this the old fashioned way so that we can have access to ``reset``
        # in the callback.
        def do_play_song(song: Child):
            # Do this the old fashioned way so that we can have access to
            # ``song`` in the callback.
            def filename_future_done(song_file):
                self.state.current_song = song
                self.state.playing = True
                self.update_window()

                # Prevent it from doing the thing where it continually loads
                # songs when it has to download.
                if reset:
                    self.had_progress_value = False
                    self.state.song_progress = 0

                self.player.command('loadfile', song_file, 'replace',
                                    f'start={self.state.song_progress}')
                self.player.pause = False

                if old_play_queue:
                    self.state.old_play_queue = old_play_queue

                if play_queue:
                    self.state.play_queue = play_queue
                    self.save_play_queue()

            def before_song_download():
                # Pause the currently playing song. This prevents anything from
                # playing while a download occurs.
                self.player.pause = True
                self.state.playing = False
                self.update_window()

            song_filename_future = CacheManager.get_song_filename(
                song, before_download=before_song_download)
            song_filename_future.add_done_callback(
                lambda f: GLib.idle_add(filename_future_done, f.result()), )

        song_details_future = CacheManager.get_song_details(song)
        song_details_future.add_done_callback(
            lambda f: GLib.idle_add(do_play_song, f.result()), )

    def save_play_queue(self):
        position = self.state.song_progress
        self.last_play_queue_update = position

        current_server = self.state.config.current_server
        current_server = self.state.config.servers[current_server]

        if current_server.sync_enabled:
            CacheManager.executor.submit(
                CacheManager.save_play_queue,
                id=self.state.play_queue,
                current=self.state.current_song.id,
                position=math.floor(position * 1000),
            )
