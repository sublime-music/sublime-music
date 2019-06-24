import math

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Pango, GObject

from libremsonic.state_manager import ApplicationState
from libremsonic.cache_manager import CacheManager
from libremsonic.ui import util


class PlayerControls(Gtk.ActionBar):
    """
    Defines the player controls panel that appears at the bottom of the window.
    """
    __gsignals__ = {
        'song-scrub': (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (float, ),
        ),
    }
    editing: bool = False

    def __init__(self):
        Gtk.ActionBar.__init__(self)
        self.set_name('player-controls-bar')

        song_display = self.create_song_display()
        playback_controls = self.create_playback_controls()
        up_next_volume = self.create_up_next_volume()

        self.pack_start(song_display)
        self.set_center_widget(playback_controls)
        self.pack_end(up_next_volume)

    def update(self, state: ApplicationState):
        icon = 'pause' if state.playing else 'start'
        self.play_button.get_child().set_from_icon_name(
            f"media-playback-{icon}-symbolic", Gtk.IconSize.LARGE_TOOLBAR)

        has_current_song = hasattr(state, 'current_song')
        has_prev_song, has_next_song = False, False
        if has_current_song:
            # TODO will need to change when repeat is implemented
            has_prev_song = state.play_queue.index(state.current_song) > 0
            has_next_song = state.play_queue.index(state.current_song) < len(
                state.play_queue) - 1

        self.song_scrubber.set_sensitive(has_current_song)
        self.repeat_button.set_sensitive(has_current_song)
        self.prev_button.set_sensitive(has_current_song and has_prev_song)
        self.play_button.set_sensitive(has_current_song)
        self.next_button.set_sensitive(has_current_song and has_next_song)
        self.shuffle_button.set_sensitive(has_current_song)

        if not has_current_song:
            return

        self.album_art.set_from_file(
            CacheManager.get_cover_art_filename(
                state.current_song.coverArt,
                size='70',
            ))

        def esc(string):
            return string.replace('&', '&amp;')

        self.song_title.set_markup(f'<b>{esc(state.current_song.title)}</b>')
        self.album_name.set_markup(f'<i>{esc(state.current_song.album)}</i>')
        self.artist_name.set_markup(f'{esc(state.current_song.artist)}')

    def update_scrubber(self, current, duration):
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

    def on_scrub_edit(self, box, event):
        print(event.x)

    def create_song_display(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.album_art = Gtk.Image()
        box.pack_start(self.album_art, False, False, 5)

        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        details_box.pack_start(Gtk.Box(), True, True, 0)

        def make_label(name):
            return Gtk.Label(
                name=name,
                halign=Gtk.Align.START,
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

        self.song_progress_label = Gtk.Label('-:--')
        scrubber_box.pack_start(self.song_progress_label, False, False, 5)

        self.song_scrubber = Gtk.Scale.new_with_range(
            orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=5)
        self.song_scrubber.set_name('song-scrubber')
        self.song_scrubber.set_draw_value(False)
        self.song_scrubber.connect('button-press-event',
                                   self.on_scrub_state_change)
        self.song_scrubber.connect('button-release-event',
                                   self.on_scrub_state_change)
        scrubber_box.pack_start(self.song_scrubber, True, True, 0)

        self.song_duration_label = Gtk.Label('-:--')
        scrubber_box.pack_start(self.song_duration_label, False, False, 5)

        box.add(scrubber_box)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        buttons.pack_start(Gtk.Box(), True, True, 0)

        # Repeat button
        self.repeat_button = util.button_with_icon(
            'media-playlist-repeat-symbolic')
        self.repeat_button.set_action_name('app.repeat-press')
        buttons.pack_start(self.repeat_button, False, False, 5)

        # Previous button
        self.prev_button = util.button_with_icon(
            'media-skip-backward-symbolic',
            icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        self.prev_button.set_action_name('app.prev-track')
        buttons.pack_start(self.prev_button, False, False, 5)

        # Play button
        self.play_button = util.button_with_icon(
            'media-playback-start-symbolic',
            relief=True,
            icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        self.play_button.set_name('play-button')
        self.play_button.set_action_name('app.play-pause')
        buttons.pack_start(self.play_button, False, False, 0)

        # Next button
        self.next_button = util.button_with_icon(
            'media-skip-forward-symbolic',
            icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        self.next_button.set_action_name('app.next-track')
        buttons.pack_start(self.next_button, False, False, 5)

        # Shuffle button
        self.shuffle_button = util.button_with_icon(
            'media-playlist-shuffle-symbolic')
        self.shuffle_button.set_action_name('app.shuffle-press')
        buttons.pack_start(self.shuffle_button, False, False, 5)

        buttons.pack_start(Gtk.Box(), True, True, 0)
        box.add(buttons)

        return box

    def create_up_next_volume(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(Gtk.Box(), True, True, 0)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        # Up Next button
        # TODO connect it to something.
        up_next_button = util.button_with_icon(
            'view-list-symbolic', icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        box.pack_start(up_next_button, False, True, 5)

        # Volume mute toggle
        # TODO connect it to something.
        self.volume_mute_toggle = util.button_with_icon('audio-volume-high')
        box.pack_start(self.volume_mute_toggle, False, True, 0)

        # Volume slider
        # TODO connect it to something.
        volume_slider = Gtk.Scale.new_with_range(
            orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=5)
        volume_slider.set_name('volume-slider')
        volume_slider.set_draw_value(False)
        volume_slider.set_value(100)
        box.pack_start(volume_slider, True, True, 0)

        vbox.pack_start(box, False, True, 0)
        vbox.pack_start(Gtk.Box(), True, True, 0)
        return vbox
