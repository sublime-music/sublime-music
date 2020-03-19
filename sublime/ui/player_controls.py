import math

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, GdkPixbuf, GLib, GObject, Gtk, Pango
from pychromecast import Chromecast

from sublime.cache_manager import CacheManager
from sublime.players import ChromecastPlayer
from sublime.server.api_objects import Child
from sublime.state_manager import ApplicationState, RepeatType
from sublime.ui import util
from sublime.ui.common import IconButton, IconToggleButton, SpinnerImage


class PlayerControls(Gtk.ActionBar):
    """
    Defines the player controls panel that appears at the bottom of the window.
    """
    __gsignals__ = {
        'song-scrub': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (float, ),
        ),
        'volume-change': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (float, ),
        ),
        'device-update': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (str, ),
        ),
        'song-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        'songs-removed': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, ),
        ),
        'refresh-window': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }
    editing: bool = False
    editing_play_queue_song_list: bool = False
    reordering_play_queue_song_list: bool = False
    current_song = None
    current_device = None
    chromecasts: List[ChromecastPlayer] = []
    cover_art_update_order_token = 0
    play_queue_update_order_token = 0
    devices_requested = False

    def __init__(self):
        Gtk.ActionBar.__init__(self)
        self.set_name('player-controls-bar')

        song_display = self.create_song_display()
        playback_controls = self.create_playback_controls()
        play_queue_volume = self.create_play_queue_volume()

        self.last_device_list_update = None

        self.pack_start(song_display)
        self.set_center_widget(playback_controls)
        self.pack_end(play_queue_volume)

    def update(self, state: ApplicationState):
        self.current_device = state.current_device

        self.update_scrubber(
            getattr(state, 'song_progress', None),
            getattr(state.current_song, 'duration', None),
        )

        icon = 'pause' if state.playing else 'start'
        self.play_button.set_icon(f"media-playback-{icon}-symbolic")
        self.play_button.set_tooltip_text('Pause' if state.playing else 'Play')

        has_current_song = state.current_song is not None
        has_next_song = False
        if state.repeat_type in (RepeatType.REPEAT_QUEUE,
                                 RepeatType.REPEAT_SONG):
            has_next_song = True
        elif has_current_song:
            has_next_song = (
                state.current_song_index < len(state.play_queue) - 1)

        # Toggle button states.
        self.repeat_button.set_action_name(None)
        self.shuffle_button.set_action_name(None)
        repeat_on = state.repeat_type in (
            RepeatType.REPEAT_QUEUE, RepeatType.REPEAT_SONG)
        self.repeat_button.set_active(repeat_on)
        self.repeat_button.set_icon(state.repeat_type.icon)
        self.shuffle_button.set_active(state.shuffle_on)
        self.repeat_button.set_action_name('app.repeat-press')
        self.shuffle_button.set_action_name('app.shuffle-press')

        self.song_scrubber.set_sensitive(has_current_song)
        self.prev_button.set_sensitive(has_current_song)
        self.play_button.set_sensitive(has_current_song)
        self.next_button.set_sensitive(has_current_song and has_next_song)

        # Volume button and slider
        if state.is_muted:
            icon_name = 'muted'
        elif state.volume < 30:
            icon_name = 'low'
        elif state.volume < 70:
            icon_name = 'medium'
        else:
            icon_name = 'high'

        self.volume_mute_toggle.set_icon(f'audio-volume-{icon_name}-symbolic')

        self.editing = True
        self.volume_slider.set_value(0 if state.is_muted else state.volume)
        self.editing = False

        # Update the current song information.
        # TODO (#126): add popup of bigger cover art photo here
        if state.current_song is not None:
            self.cover_art_update_order_token += 1
            self.update_cover_art(
                state.current_song.coverArt,
                order_token=self.cover_art_update_order_token,
            )

            self.song_title.set_markup(util.esc(state.current_song.title))
            self.album_name.set_markup(util.esc(state.current_song.album))
            artist_name = util.esc(state.current_song.artist)
            self.artist_name.set_markup(artist_name or '')
        else:
            # Clear out the cover art and song tite if no song
            self.album_art.set_from_file(None)
            self.album_art.set_loading(False)
            self.song_title.set_markup('')
            self.album_name.set_markup('')
            self.artist_name.set_markup('')

        if self.devices_requested:
            self.update_device_list()

        # Set the Play Queue button popup.
        if hasattr(state, 'play_queue'):
            play_queue_len = len(state.play_queue)
            if play_queue_len == 0:
                self.popover_label.set_markup('<b>Play Queue</b>')
            else:
                song_label = util.pluralize('song', play_queue_len)
                self.popover_label.set_markup(
                    f'<b>Play Queue:</b> {play_queue_len} {song_label}')

            self.editing_play_queue_song_list = True

            new_store = []

            def calculate_label(song_details: Child) -> str:
                title = util.esc(song_details.title)
                album = util.esc(song_details.album)
                artist = util.esc(song_details.artist)
                return f'<b>{title}</b>\n{util.dot_join(album, artist)}'

            def make_idle_index_capturing_function(
                idx: int,
                order_tok: int,
                fn: Callable[[int, int, Any], None],
            ) -> Callable[[CacheManager.Result], None]:
                return lambda f: GLib.idle_add(fn, idx, order_tok, f.result())

            def on_cover_art_future_done(
                idx: int,
                order_token: int,
                cover_art_filename: str,
            ):
                if order_token != self.play_queue_update_order_token:
                    return

                self.play_queue_store[idx][0] = cover_art_filename

            def on_song_details_future_done(
                idx: int,
                order_token: int,
                song_details: Child,
            ):
                if order_token != self.play_queue_update_order_token:
                    return

                self.play_queue_store[idx][1] = calculate_label(song_details)

                # Cover Art
                cover_art_result = CacheManager.get_cover_art_filename(
                    song_details.coverArt)
                if cover_art_result.is_future:
                    # We don't have the cover art already cached.
                    cover_art_result.add_done_callback(
                        make_idle_index_capturing_function(
                            idx,
                            order_token,
                            on_cover_art_future_done,
                        ))
                else:
                    # We have the cover art already cached.
                    self.play_queue_store[idx][0] = cover_art_result.result()

            if state.play_queue != [x[-1] for x in self.play_queue_store]:
                self.play_queue_update_order_token += 1

            song_details_results = []
            for i, song_id in enumerate(state.play_queue):
                song_details_result = CacheManager.get_song_details(song_id)

                cover_art_filename = ''
                label = '\n'

                if song_details_result.is_future:
                    song_details_results.append((i, song_details_result))
                else:
                    # We have the details of the song already cached.
                    song_details = song_details_result.result()
                    label = calculate_label(song_details)

                    cover_art_result = CacheManager.get_cover_art_filename(
                        song_details.coverArt)
                    if cover_art_result.is_future:
                        # We don't have the cover art already cached.
                        cover_art_result.add_done_callback(
                            make_idle_index_capturing_function(
                                i,
                                self.play_queue_update_order_token,
                                on_cover_art_future_done,
                            ))
                    else:
                        # We have the cover art already cached.
                        cover_art_filename = cover_art_result.result()

                new_store.append(
                    [
                        cover_art_filename,
                        label,
                        i == state.current_song_index,
                        song_id,
                    ])

            util.diff_song_store(self.play_queue_store, new_store)

            # Do this after the diff to avoid race conditions.
            for idx, song_details_result in song_details_results:
                song_details_result.add_done_callback(
                    make_idle_index_capturing_function(
                        idx,
                        self.play_queue_update_order_token,
                        on_song_details_future_done,
                    ))

            self.editing_play_queue_song_list = False

    @util.async_callback(
        lambda *k, **v: CacheManager.get_cover_art_filename(*k, **v),
        before_download=lambda self: self.album_art.set_loading(True),
        on_failure=lambda self, e: self.album_art.set_loading(False),
    )
    def update_cover_art(
        self,
        cover_art_filename: str,
        state: ApplicationState,
        force: bool = False,
        order_token: int = None,
    ):
        if order_token != self.cover_art_update_order_token:
            return

        self.album_art.set_from_file(cover_art_filename)
        self.album_art.set_loading(False)

    def update_scrubber(self, current: float, duration: int):
        if current is None or duration is None:
            self.song_duration_label.set_text('-:--')
            self.song_progress_label.set_text('-:--')
            self.song_scrubber.set_value(0)
            return

        current = current or 0
        percent_complete = current / duration * 100

        if not self.editing:
            self.song_scrubber.set_value(percent_complete)
        self.song_duration_label.set_text(util.format_song_duration(duration))
        self.song_progress_label.set_text(
            util.format_song_duration(math.floor(current)))

    def on_volume_change(self, scale: Gtk.Scale):
        if not self.editing:
            self.emit('volume-change', scale.get_value())

    def on_play_queue_click(self, _: Any):
        if self.play_queue_popover.is_visible():
            self.play_queue_popover.popdown()
        else:
            # TODO (#88): scroll the currently playing song into view.
            self.play_queue_popover.popup()
            self.play_queue_popover.show_all()

    def on_song_activated(self, t: Any, idx: Gtk.TreePath, c: Any):
        # The song ID is in the last column of the model.
        self.emit(
            'song-clicked',
            idx.get_indices()[0],
            [m[-1] for m in self.play_queue_store],
            {'no_reshuffle': True},
        )

    def update_device_list(self, force: bool = False):
        self.device_list_loading.show()

        def chromecast_callback(chromecasts: List[Chromecast]):
            self.chromecasts = chromecasts
            for c in self.chromecast_device_list.get_children():
                self.chromecast_device_list.remove(c)

            if self.current_device == 'this device':
                self.this_device.set_icon('audio-volume-high-symbolic')
            else:
                self.this_device.set_icon(None)

            chromecasts.sort(key=lambda c: c.device.friendly_name)
            for cc in chromecasts:
                icon = (
                    'audio-volume-high-symbolic'
                    if str(cc.device.uuid) == self.current_device else None)
                btn = IconButton(icon, label=cc.device.friendly_name)
                btn.get_style_context().add_class('menu-button')
                btn.connect(
                    'clicked',
                    lambda _, uuid: self.emit('device-update', uuid),
                    cc.device.uuid,
                )
                self.chromecast_device_list.add(btn)
                self.chromecast_device_list.show_all()

            self.device_list_loading.hide()
            self.last_device_list_update = datetime.now()

        update_diff = (
            self.last_device_list_update
            and (datetime.now() - self.last_device_list_update).seconds > 60)
        if (force or len(self.chromecasts) == 0
                or (update_diff and update_diff > 60)):
            future = ChromecastPlayer.get_chromecasts()
            future.add_done_callback(
                lambda f: GLib.idle_add(chromecast_callback, f.result()))
        else:
            chromecast_callback(self.chromecasts)

    def on_device_click(self, _: Any):
        self.devices_requested = True
        if self.device_popover.is_visible():
            self.device_popover.popdown()
        else:
            self.device_popover.popup()
            self.device_popover.show_all()
            self.update_device_list()

    def on_device_refresh_click(self, _: Any):
        self.update_device_list(force=True)

    def on_play_queue_button_press(
            self,
            tree: Any,
            event: Gdk.EventButton,
    ) -> bool:
        if event.button == 3:  # Right click
            clicked_path = tree.get_path_at_pos(event.x, event.y)

            store, paths = tree.get_selection().get_selected_rows()
            allow_deselect = False

            def on_download_state_change(song_id: int = None):
                # Refresh the entire window (no force) because the song could
                # be in a list anywhere in the window.
                self.emit('refresh-window', {}, False)

            # Use the new selection instead of the old one for calculating what
            # to do the right click on.
            if clicked_path[0] not in paths:
                paths = [clicked_path[0]]
                allow_deselect = True

            song_ids = [self.play_queue_store[p][-1] for p in paths]

            remove_text = (
                'Remove ' + util.pluralize('song', len(song_ids))
                + ' from queue')

            def on_remove_songs_click(_: Any):
                self.emit('songs-removed', [p.get_indices()[0] for p in paths])

            util.show_song_popover(
                song_ids,
                event.x,
                event.y,
                tree,
                on_download_state_change=on_download_state_change,
                extra_menu_items=[
                    (Gtk.ModelButton(text=remove_text), on_remove_songs_click),
                ],
            )

            # If the click was on a selected row, don't deselect anything.
            if not allow_deselect:
                return True

        return False

    def on_play_queue_model_row_move(self, *args):
        # If we are programatically editing the song list, don't do anything.
        if self.editing_play_queue_song_list:
            return

        # We get both a delete and insert event, I think it's deterministic
        # which one comes first, but just in case, we have this
        # reordering_play_queue_song_list flag.
        if self.reordering_play_queue_song_list:
            currently_playing_index = [
                i for i, s in enumerate(self.play_queue_store) if s[2]
            ][0]
            self.emit(
                'refresh-window',
                {
                    'current_song_index': currently_playing_index,
                    'play_queue': [s[-1] for s in self.play_queue_store],
                },
                False,
            )
            self.reordering_play_queue_song_list = False
        else:
            self.reordering_play_queue_song_list = True

    def create_song_display(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.album_art = SpinnerImage(
            image_name='player-controls-album-artwork',
            image_size=70,
        )
        box.pack_start(self.album_art, False, False, 5)

        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        details_box.pack_start(Gtk.Box(), True, True, 0)

        def make_label(name: str) -> Gtk.Label:
            return Gtk.Label(
                name=name,
                halign=Gtk.Align.START,
                xalign=0,
                use_markup=True,
                ellipsize=Pango.EllipsizeMode.END,
            )

        self.song_title = make_label('song-title')
        details_box.add(self.song_title)

        self.album_name = make_label('album-name')
        details_box.add(self.album_name)

        self.artist_name = make_label('artist-name')
        details_box.add(self.artist_name)

        details_box.pack_start(Gtk.Box(), True, True, 0)
        box.pack_start(details_box, False, False, 5)

        return box

    def create_playback_controls(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Scrubber and song progress/length labels
        scrubber_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.song_progress_label = Gtk.Label(label='-:--')
        scrubber_box.pack_start(self.song_progress_label, False, False, 5)

        self.song_scrubber = Gtk.Scale.new_with_range(
            orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=5)
        self.song_scrubber.set_name('song-scrubber')
        self.song_scrubber.set_draw_value(False)
        self.song_scrubber.connect(
            'change-value', lambda s, t, v: self.emit('song-scrub', v))
        scrubber_box.pack_start(self.song_scrubber, True, True, 0)

        self.song_duration_label = Gtk.Label(label='-:--')
        scrubber_box.pack_start(self.song_duration_label, False, False, 5)

        box.add(scrubber_box)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        buttons.pack_start(Gtk.Box(), True, True, 0)

        # Repeat button
        repeat_button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.repeat_button = IconToggleButton(
            'media-playlist-repeat', 'Switch between repeat modes')
        self.repeat_button.set_action_name('app.repeat-press')
        repeat_button_box.pack_start(Gtk.Box(), True, True, 0)
        repeat_button_box.pack_start(self.repeat_button, False, False, 0)
        repeat_button_box.pack_start(Gtk.Box(), True, True, 0)
        buttons.pack_start(repeat_button_box, False, False, 5)

        # Previous button
        self.prev_button = IconButton(
            'media-skip-backward-symbolic',
            'Go to previous song',
            icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        self.prev_button.set_action_name('app.prev-track')
        buttons.pack_start(self.prev_button, False, False, 5)

        # Play button
        self.play_button = IconButton(
            'media-playback-start-symbolic',
            'Play',
            relief=True,
            icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        self.play_button.set_name('play-button')
        self.play_button.set_action_name('app.play-pause')
        buttons.pack_start(self.play_button, False, False, 0)

        # Next button
        self.next_button = IconButton(
            'media-skip-forward-symbolic',
            'Go to next song',
            icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        self.next_button.set_action_name('app.next-track')
        buttons.pack_start(self.next_button, False, False, 5)

        # Shuffle button
        shuffle_button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.shuffle_button = IconToggleButton(
            'media-playlist-shuffle-symbolic', 'Toggle playlist shuffling')
        self.shuffle_button.set_action_name('app.shuffle-press')
        shuffle_button_box.pack_start(Gtk.Box(), True, True, 0)
        shuffle_button_box.pack_start(self.shuffle_button, False, False, 0)
        shuffle_button_box.pack_start(Gtk.Box(), True, True, 0)
        buttons.pack_start(shuffle_button_box, False, False, 5)

        buttons.pack_start(Gtk.Box(), True, True, 0)
        box.add(buttons)

        return box

    def create_play_queue_volume(self) -> Gtk.Box:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(Gtk.Box(), True, True, 0)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        # Device button (for chromecast)
        self.device_button = IconButton(
            'video-display-symbolic',
            'Show available audio output devices',
            icon_size=Gtk.IconSize.LARGE_TOOLBAR,
        )
        self.device_button.connect('clicked', self.on_device_click)
        box.pack_start(self.device_button, False, True, 5)

        self.device_popover = Gtk.PopoverMenu(
            modal=False,
            name='device-popover',
        )
        self.device_popover.set_relative_to(self.device_button)

        device_popover_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            name='device-popover-box',
        )
        device_popover_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.popover_label = Gtk.Label(
            label='<b>Devices</b>',
            use_markup=True,
            halign=Gtk.Align.START,
            margin=5,
        )
        device_popover_header.add(self.popover_label)

        refresh_devices = IconButton(
            'view-refresh-symbolic', 'Refresh device list')
        refresh_devices.connect('clicked', self.on_device_refresh_click)
        device_popover_header.pack_end(refresh_devices, False, False, 0)

        device_popover_box.add(device_popover_header)

        device_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.this_device = IconButton(
            'audio-volume-high-symbolic',
            label='This Device',
        )
        self.this_device.get_style_context().add_class('menu-button')
        self.this_device.connect(
            'clicked', lambda *a: self.emit('device-update', 'this device'))
        device_list.add(self.this_device)

        device_list.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self.device_list_loading = Gtk.Spinner(active=True)
        self.device_list_loading.get_style_context().add_class('menu-button')
        device_list.add(self.device_list_loading)

        self.chromecast_device_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL)
        device_list.add(self.chromecast_device_list)

        device_popover_box.pack_end(device_list, True, True, 0)

        self.device_popover.add(device_popover_box)

        # Play Queue button
        self.play_queue_button = IconButton(
            'view-list-symbolic',
            'Open play queue',
            icon_size=Gtk.IconSize.LARGE_TOOLBAR,
        )
        self.play_queue_button.connect('clicked', self.on_play_queue_click)
        box.pack_start(self.play_queue_button, False, True, 5)

        self.play_queue_popover = Gtk.PopoverMenu(
            modal=False,
            name='up-next-popover',
        )
        self.play_queue_popover.set_relative_to(self.play_queue_button)

        play_queue_popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        play_queue_popover_header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL)

        self.popover_label = Gtk.Label(
            label='<b>Play Queue</b>',
            use_markup=True,
            halign=Gtk.Align.START,
            margin=10,
        )
        play_queue_popover_header.add(self.popover_label)

        load_play_queue = IconButton(
            'folder-download-symbolic', 'Load Queue from Server', margin=5)
        load_play_queue.set_action_name('app.update-play-queue-from-server')
        play_queue_popover_header.pack_end(load_play_queue, False, False, 0)

        play_queue_popover_box.add(play_queue_popover_header)

        play_queue_scrollbox = Gtk.ScrolledWindow(
            min_content_height=600,
            min_content_width=400,
        )

        self.play_queue_store = Gtk.ListStore(
            str,  # image filename
            str,  # title, album, artist
            bool,  # playing
            str,  # song ID
        )
        self.play_queue_list = Gtk.TreeView(
            model=self.play_queue_store,
            reorderable=True,
            headers_visible=False,
        )
        self.play_queue_list.get_selection().set_mode(
            Gtk.SelectionMode.MULTIPLE)

        # Album Art column.
        def filename_to_pixbuf(
            column: Any,
            cell: Gtk.CellRendererPixbuf,
            model: Gtk.ListStore,
            iter: Gtk.TreeIter,
            flags: Any,
        ):
            filename = model.get_value(iter, 0)
            if not filename:
                cell.set_property('icon_name', '')
                return
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                filename, 50, 50, True)

            # If this is the playing song, then overlay the play icon.
            if model.get_value(iter, 2):
                play_overlay_pixbuf = GdkPixbuf.Pixbuf.new_from_file(
                    str(
                        Path(__file__).parent.joinpath(
                            'images/play-queue-play.png')))

                play_overlay_pixbuf.composite(
                    pixbuf, 0, 0, 50, 50, 0, 0, 1, 1,
                    GdkPixbuf.InterpType.NEAREST, 255)

            cell.set_property('pixbuf', pixbuf)

        renderer = Gtk.CellRendererPixbuf()
        renderer.set_fixed_size(55, 60)
        column = Gtk.TreeViewColumn('', renderer)
        column.set_cell_data_func(renderer, filename_to_pixbuf)
        column.set_resizable(True)
        self.play_queue_list.append_column(column)

        renderer = Gtk.CellRendererText(
            markup=True,
            ellipsize=Pango.EllipsizeMode.END,
        )
        column = Gtk.TreeViewColumn('', renderer, markup=1)
        self.play_queue_list.append_column(column)

        self.play_queue_list.connect('row-activated', self.on_song_activated)
        self.play_queue_list.connect(
            'button-press-event', self.on_play_queue_button_press)

        # Set up drag-and-drop on the song list for editing the order of the
        # playlist.
        self.play_queue_store.connect(
            'row-inserted', self.on_play_queue_model_row_move)
        self.play_queue_store.connect(
            'row-deleted', self.on_play_queue_model_row_move)

        play_queue_scrollbox.add(self.play_queue_list)
        play_queue_popover_box.pack_end(play_queue_scrollbox, True, True, 0)

        self.play_queue_popover.add(play_queue_popover_box)

        # Volume mute toggle
        self.volume_mute_toggle = IconButton(
            'audio-volume-high-symbolic', 'Toggle mute')
        self.volume_mute_toggle.set_action_name('app.mute-toggle')
        box.pack_start(self.volume_mute_toggle, False, True, 0)

        # Volume slider
        self.volume_slider = Gtk.Scale.new_with_range(
            orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=5)
        self.volume_slider.set_name('volume-slider')
        self.volume_slider.set_draw_value(False)
        self.volume_slider.connect('value-changed', self.on_volume_change)
        box.pack_start(self.volume_slider, True, True, 0)

        vbox.pack_start(box, False, True, 0)
        vbox.pack_start(Gtk.Box(), True, True, 0)
        return vbox
