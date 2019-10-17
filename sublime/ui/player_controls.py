import math

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Pango, GObject, Gio, GLib

from sublime.cache_manager import CacheManager
from sublime.state_manager import ApplicationState, RepeatType
from sublime.ui import util
from sublime.ui.common import IconButton, SpinnerImage
from sublime.ui.common.players import ChromecastPlayer


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
            (str, object, object),
        ),
    }
    editing: bool = False
    current_song = None

    class PlayQueueSong(GObject.GObject):
        song_id = GObject.Property(type=str)
        playing = GObject.Property(type=str)

        def __init__(self, song_id: str, playing: bool):
            GObject.GObject.__init__(self)
            self.song_id = song_id
            self.playing = str(playing)

    def __init__(self):
        Gtk.ActionBar.__init__(self)
        self.set_name('player-controls-bar')

        song_display = self.create_song_display()
        playback_controls = self.create_playback_controls()
        play_queue_volume = self.create_play_queue_volume()

        self.pack_start(song_display)
        self.set_center_widget(playback_controls)
        self.pack_end(play_queue_volume)

    def update(self, state: ApplicationState):
        self.update_scrubber(
            getattr(state, 'song_progress', None),
            getattr(state.current_song, 'duration', None),
        )

        icon = 'pause' if state.playing else 'start'
        self.play_button.set_icon(f"media-playback-{icon}-symbolic")

        has_current_song = (
            hasattr(state, 'current_song') and state.current_song is not None)
        has_next_song = False
        if state.repeat_type in (RepeatType.REPEAT_QUEUE,
                                 RepeatType.REPEAT_SONG):
            has_next_song = True
        elif has_current_song and state.current_song.id in state.play_queue:
            current = state.play_queue.index(state.current_song.id)
            has_next_song = current < len(state.play_queue) - 1

        # Repeat button state
        # TODO: it's not correct to use symboloc vs. not symbolic icons for
        # lighter/darker versions of the icon. Fix this by using FG color I
        # think? But then we have to deal with styling, which sucks.
        self.repeat_button.set_icon(state.repeat_type.icon)

        # Shuffle button state
        # TODO: it's not correct to use symboloc vs. not symbolic icons for
        # lighter/darker versions of the icon. Fix this by using FG color I
        # think? But then we have to deal with styling, which sucks.
        self.shuffle_button.set_icon(
            'media-playlist-shuffle'
            + ('-symbolic' if state.shuffle_on else ''))

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

        self.volume_mute_toggle.set_icon('audio-volume-' + icon_name)

        self.editing = True
        self.volume_slider.set_value(0 if state.is_muted else state.volume)
        self.editing = False

        # Update the current song information.
        # TODO add popup of bigger cover art photo here
        if has_current_song:
            self.update_cover_art(state.current_song.coverArt, size='70')

            self.song_title.set_text(util.esc(state.current_song.title))
            self.album_name.set_text(util.esc(state.current_song.album))
            artist_name = util.esc(state.current_song.artist)
            self.artist_name.set_text(artist_name or '')
        else:
            # Clear out the cover art and song tite if no song
            self.album_art.set_from_file(None)
            self.song_title.set_text('')
            self.album_name.set_text('')
            self.artist_name.set_text('')
            self.album_art.set_loading(False)

        # Set the Play Queue button popup.
        if hasattr(state, 'play_queue'):
            play_queue_len = len(state.play_queue)
            if play_queue_len == 0:
                self.popover_label.set_markup('<b>Play Queue</b>')
            else:
                song_label = util.pluralize('song', play_queue_len)
                self.popover_label.set_markup(
                    f'<b>Play Queue:</b> {play_queue_len} {song_label}')

            new_model = [
                PlayerControls.PlayQueueSong(
                    s, has_current_song and s == state.current_song.id)
                for s in state.play_queue
            ]
            util.diff_model_store(self.play_queue_store, new_model)

    @util.async_callback(
        lambda *k, **v: CacheManager.get_cover_art_filename(*k, **v),
        before_download=lambda self: self.album_art.set_loading(True),
        on_failure=lambda self, e: self.album_art.set_loading(False),
    )
    def update_cover_art(self, cover_art_filename, state):
        self.album_art.set_from_file(cover_art_filename)
        self.album_art.set_loading(False)

    def update_scrubber(self, current, duration):
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

    def on_scrub_state_change(self, scrubber_container, eventbutton):
        self.editing = not self.editing

        if not self.editing:
            self.emit('song-scrub', self.song_scrubber.get_value())

    def on_volume_change(self, scale):
        if not self.editing:
            self.emit('volume-change', scale.get_value())

    def on_play_queue_click(self, button):
        self.play_queue_popover.set_relative_to(button)
        # TODO scroll the currently playing song into view.
        self.play_queue_popover.popup()
        self.play_queue_popover.show_all()

    def update_device_list(self, clear=False):
        self.device_list_loading.show()

        def clear_list():
            for c in self.chromecast_device_list.get_children():
                self.chromecast_device_list.remove(c)

        def chromecast_callback(f):
            clear_list()
            chromecasts = f.result()
            chromecasts.sort(key=lambda c: c.device.friendly_name)
            for cc in chromecasts:
                btn = Gtk.ModelButton(text=cc.device.friendly_name)
                btn.get_style_context().add_class('menu-button')
                btn.connect(
                    'clicked',
                    lambda _, uuid: self.emit('device-update', uuid),
                    cc.device.uuid,
                )
                self.chromecast_device_list.add(btn)
                self.chromecast_device_list.show_all()

            self.device_list_loading.hide()

        if clear:
            clear_list()

        future = ChromecastPlayer.get_chromecasts()
        future.add_done_callback(
            lambda f: GLib.idle_add(chromecast_callback, f))

    def on_device_click(self, button):
        self.update_device_list()
        self.device_popover.set_relative_to(button)
        self.device_popover.popup()
        self.device_popover.show_all()

    def on_device_refresh_click(self, button):
        self.update_device_list(clear=True)

    def create_song_display(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.album_art = SpinnerImage(
            image_name='player-controls-album-artwork')
        box.pack_start(self.album_art, False, False, 5)

        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        details_box.pack_start(Gtk.Box(), True, True, 0)

        def make_label(name):
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

    def create_playback_controls(self):
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
            'button-press-event', self.on_scrub_state_change)
        self.song_scrubber.connect(
            'button-release-event', self.on_scrub_state_change)
        scrubber_box.pack_start(self.song_scrubber, True, True, 0)

        self.song_duration_label = Gtk.Label(label='-:--')
        scrubber_box.pack_start(self.song_duration_label, False, False, 5)

        box.add(scrubber_box)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        buttons.pack_start(Gtk.Box(), True, True, 0)

        # Repeat button
        self.repeat_button = IconButton('media-playlist-repeat')
        self.repeat_button.set_action_name('app.repeat-press')
        buttons.pack_start(self.repeat_button, False, False, 5)

        # Previous button
        self.prev_button = IconButton(
            'media-skip-backward-symbolic',
            icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        self.prev_button.set_action_name('app.prev-track')
        buttons.pack_start(self.prev_button, False, False, 5)

        # Play button
        self.play_button = IconButton(
            'media-playback-start-symbolic',
            relief=True,
            icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        self.play_button.set_name('play-button')
        self.play_button.set_action_name('app.play-pause')
        buttons.pack_start(self.play_button, False, False, 0)

        # Next button
        self.next_button = IconButton(
            'media-skip-forward-symbolic',
            icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        self.next_button.set_action_name('app.next-track')
        buttons.pack_start(self.next_button, False, False, 5)

        # Shuffle button
        self.shuffle_button = IconButton('media-playlist-shuffle')
        self.shuffle_button.set_action_name('app.shuffle-press')
        buttons.pack_start(self.shuffle_button, False, False, 5)

        buttons.pack_start(Gtk.Box(), True, True, 0)
        box.add(buttons)

        return box

    def create_play_queue_volume(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(Gtk.Box(), True, True, 0)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        # Device button (for chromecast)
        # TODO need icon
        device_button = IconButton(
            'view-list-symbolic', icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        device_button.connect('clicked', self.on_device_click)
        box.pack_start(device_button, False, True, 5)

        self.device_popover = Gtk.PopoverMenu(name='device-popover')

        device_popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        device_popover_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.popover_label = Gtk.Label(
            label='<b>Devices</b>',
            use_markup=True,
            halign=Gtk.Align.START,
            margin=5,
        )
        device_popover_header.add(self.popover_label)

        refresh_devices = IconButton('view-refresh')
        refresh_devices.connect('clicked', self.on_device_refresh_click)
        device_popover_header.pack_end(refresh_devices, False, False, 0)

        device_popover_box.add(device_popover_header)

        device_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        this_device = Gtk.ModelButton(text='This Device')
        this_device.get_style_context().add_class('menu-button')
        this_device.connect(
            'clicked', lambda *a: self.emit('device-update', 'this device'))
        device_list.add(this_device)

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
        play_queue_button = IconButton(
            'view-list-symbolic', icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        play_queue_button.connect('clicked', self.on_play_queue_click)
        box.pack_start(play_queue_button, False, True, 5)

        self.play_queue_popover = Gtk.PopoverMenu(name='up-next-popover')

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

        load_play_queue = Gtk.Button(label='Load Queue from Server', margin=5)
        load_play_queue.set_action_name('app.update-play-queue-from-server')
        play_queue_popover_header.pack_end(load_play_queue, False, False, 0)

        play_queue_popover_box.add(play_queue_popover_header)

        play_queue_scrollbox = Gtk.ScrolledWindow(
            min_content_height=600,
            min_content_width=400,
        )

        self.play_queue_store = Gio.ListStore()
        self.play_queue_list = Gtk.ListBox(activate_on_single_click=False)
        self.play_queue_list.bind_model(
            self.play_queue_store,
            self.create_play_queue_row,
        )

        play_queue_scrollbox.add(self.play_queue_list)
        play_queue_popover_box.pack_end(play_queue_scrollbox, True, True, 0)

        self.play_queue_popover.add(play_queue_popover_box)

        # Volume mute toggle
        self.volume_mute_toggle = IconButton('audio-volume-high')
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

    def create_play_queue_row(self, model: PlayQueueSong):
        row = Gtk.ListBoxRow(
            action_name='app.play-queue-click',
            action_target=GLib.Variant('s', model.song_id),
        )
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, margin=3)

        overlay = Gtk.Overlay()
        image = SpinnerImage(image_name='play-queue-row-image')
        overlay.add(image)
        box.add(overlay)

        # Add a play icon overlay if this is the currently playing song.
        if model.playing == 'True':
            # TODO style this with a a border so that it is visible when the
            # cover art looks similar.
            play_icon = Gtk.Image(
                name='play-queue-playing-icon',
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
            )
            play_icon.set_from_icon_name(
                'media-playback-start-symbolic',
                Gtk.IconSize.DIALOG,
            )
            overlay.add_overlay(play_icon)

        label = Gtk.Label(
            label='\n',
            use_markup=True,
            margin=10,
            halign=Gtk.Align.START,
            ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=35,
        )
        box.add(label)
        row.add(box)

        def update_image(image_filename):
            image.set_from_file(image_filename)
            image.set_loading(False)
            row.show_all()

        def update_row(song_details):
            title = util.esc(song_details.title)
            album = util.esc(song_details.album)
            artist = util.esc(song_details.artist)
            label.set_markup(f'<b>{title}</b>\n{util.dot_join(album, artist)}')
            row.show_all()

            cover_art_future = CacheManager.get_cover_art_filename(
                song_details.coverArt, size=50)
            cover_art_future.add_done_callback(
                lambda f: GLib.idle_add(update_image, f.result()))

        song_details_future = CacheManager.get_song_details(model.song_id)
        song_details_future.add_done_callback(
            lambda f: GLib.idle_add(update_row, f.result()))

        row.show_all()
        return row
