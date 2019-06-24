import os
from typing import List

import mpv

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, GLib, Gdk, GObject

from .ui.main import MainWindow
from .ui.configure_servers import ConfigureServersDialog
from .ui import util

from .state_manager import ApplicationState
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

        self.player = mpv.MPV()

        @self.player.property_observer('time-pos')
        def time_observer(_name, value):
            GLib.idle_add(
                self.window.player_controls.update_scrubber,
                value,
                self.state.current_song.duration,
            )

        @self.player.property_observer('eof-reached')
        def file_end(_, value):
            print('eof', value)
            return
            if value is None:
                # TODO handle repeat
                current_idx = self.state.play_queue.index(
                    self.state.current_song)
                has_next_song = current_idx < len(self.state.play_queue) - 1
                if has_next_song:
                    self.on_next_track(None, None)

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

        # Display the window.
        self.window.show_all()
        self.window.present()

        # Load the configuration and update the UI with the curent server, if
        # it exists.
        self.state.load_config()

        # If there is no current server, show the dialog to select a server.
        if self.state.config.current_server is None:
            self.show_configure_servers_dialog()
        else:
            self.on_connected_server_changed(
                None,
                self.state.config.current_server,
            )

    # ########## ACTION HANDLERS ########## #
    def on_configure_servers(self, action, param):
        self.show_configure_servers_dialog()

    def on_play_pause(self, action, param):
        self.player.cycle('pause')
        self.state.playing = not self.state.playing

        self.update_window()

    def on_next_track(self, action, params):
        current_idx = self.state.play_queue.index(self.state.current_song.id)
        self.play_song(self.state.play_queue[current_idx + 1])

    def on_prev_track(self, action, params):
        current_idx = self.state.play_queue.index(self.state.current_song.id)
        self.play_song(self.state.play_queue[current_idx - 1])

    def on_repeat_press(self, action, params):
        print('repeat press')

    def on_shuffle_press(self, action, params):
        print('shuffle press')

    def on_server_list_changed(self, action, servers):
        self.state.config.servers = servers
        self.state.save_config()

    def on_connected_server_changed(self, action, current_server):
        self.state.config.current_server = current_server
        self.state.save_config()

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
        CacheManager.executor.submit(lambda: CacheManager.save_play_queue(
            id=song_queue, current=song_id))
        self.state.play_queue = song_queue
        self.play_song(song_id)

    def on_song_scrub(self, _, scrub_value):
        if not hasattr(self.state, 'current_song'):
            return

        new_time = self.state.current_song.duration * (scrub_value / 100)
        self.player.command('seek', str(new_time), 'absolute')

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

    @util.async_callback(
        lambda *a, **k: CacheManager.get_song_details(*a, **k),
    )
    def play_song(self, song: Child):
        self.state.playing = True

        song_filename_future = CacheManager.get_song_filename(song)

        def filename_future_done(song_file):
            self.state.current_song = song
            self.update_window()
            self.player.loadfile(song_file, 'replace')
            self.player.pause = False

        song_filename_future.add_done_callback(
            lambda f: GLib.idle_add(filename_future_done, f.result()), )
