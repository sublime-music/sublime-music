import math

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Pango, GObject, Gio, GLib

from libremsonic.state_manager import ApplicationState, RepeatType
from libremsonic.cache_manager import CacheManager
from libremsonic.ui import util


class PlayerControls(Gtk.ActionBar):
    """
    Defines the player controls panel that appears at the bottom of the window.
    """
    __gsignals__ = {
        'song-scrub':
        (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (float, )),
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
        if hasattr(state, 'current_song') and state.current_song is not None:
            self.update_scrubber(state.song_progress,
                                 state.current_song.duration)

        icon = 'pause' if state.playing else 'start'
        self.play_button.get_child().set_from_icon_name(
            f"media-playback-{icon}-symbolic", Gtk.IconSize.LARGE_TOOLBAR)

        has_current_song = (hasattr(state, 'current_song')
                            and state.current_song is not None)
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
        icon = Gio.ThemedIcon(name=state.repeat_type.icon)
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        self.repeat_button.remove(self.repeat_button.get_child())
        self.repeat_button.add(image)
        self.repeat_button.show_all()

        # Shuffle button state
        # TODO: it's not correct to use symboloc vs. not symbolic icons for
        # lighter/darker versions of the icon. Fix this by using FG color I
        # think? But then we have to deal with styling, which sucks.
        icon = Gio.ThemedIcon(name='media-playlist-shuffle'
                              + ('-symbolic' if state.shuffle_on else ''))
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        self.shuffle_button.remove(self.shuffle_button.get_child())
        self.shuffle_button.add(image)
        self.shuffle_button.show_all()

        self.song_scrubber.set_sensitive(has_current_song)
        self.prev_button.set_sensitive(has_current_song)
        self.play_button.set_sensitive(has_current_song)
        self.next_button.set_sensitive(has_current_song and has_next_song)

        # Volume button and slider
        if state.volume == 0:
            icon_name = 'muted'
        elif state.volume < 30:
            icon_name = 'low'
        elif state.volume < 70:
            icon_name = 'medium'
        else:
            icon_name = 'high'

        icon = Gio.ThemedIcon(name='audio-volume-' + icon_name)
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        self.volume_mute_toggle.remove(self.volume_mute_toggle.get_child())
        self.volume_mute_toggle.add(image)
        self.volume_mute_toggle.show_all()

        self.volume_slider.set_value(state.volume)

        # Update the current song information.
        # TODO add popup to something here
        if has_current_song:
            # TODO should probably clear out the cover art display if no song??
            self.update_cover_art(state.current_song.coverArt, size='70')

            self.song_title.set_text(util.esc(state.current_song.title))
            self.album_name.set_text(util.esc(state.current_song.album))
            self.artist_name.set_text(util.esc(state.current_song.artist))

        # Set the Up Next button popup.
        if hasattr(state, 'play_queue'):
            play_queue_len = len(state.play_queue)
            if play_queue_len == 0:
                self.popover_label.set_markup('<b>Up Next</b>')
            else:
                song_label = str(play_queue_len) + ' ' + util.pluralize(
                    'song', play_queue_len)
                self.popover_label.set_markup(f'<b>Up Next:</b> {song_label}')

            # Remove everything from the play queue.
            for c in self.popover_list.get_children():
                self.popover_list.remove(c)

            for s in state.play_queue:
                self.popover_list.add(
                    Gtk.Label(
                        halign=Gtk.Align.START,
                        use_markup=True,
                        margin=5,
                    ))

            self.popover_list.show_all()

            # These are normally already have been retrieved, so should be no
            # cost for doing the ``get_song_details`` call.
            for i, song_id in enumerate(state.play_queue):
                # Create a function to capture the value of i for the inner
                # function. This outer function creates the actual callback
                # function.
                def update_fn_generator(i):
                    def do_update_label(result):
                        title = util.esc(result.title)
                        album = util.esc(result.album)
                        row = self.popover_list.get_row_at_index(i)
                        row.get_child().set_markup(f'<b>{title}</b>\n{album}')
                        row.show_all()

                    return lambda f: GLib.idle_add(do_update_label, f.result())

                future = CacheManager.get_song_details(song_id, lambda: None)
                future.add_done_callback(update_fn_generator(i))

    @util.async_callback(
        lambda *k, **v: CacheManager.get_cover_art_filename(*k, **v),
        before_download=lambda self: print('set loading here'),
        on_failure=lambda self, e: print('stop loading here'),
    )
    def update_cover_art(self, cover_art_filename):
        self.album_art.set_from_file(cover_art_filename)

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

    def on_up_next_click(self, button):
        self.up_next_popover.set_relative_to(button)
        self.up_next_popover.popup()
        self.up_next_popover.show_all()

    def create_song_display(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.album_art = Gtk.Image(name="player-controls-album-artwork")
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

        self.song_progress_label = Gtk.Label(label='-:--')
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

        self.song_duration_label = Gtk.Label(label='-:--')
        scrubber_box.pack_start(self.song_duration_label, False, False, 5)

        box.add(scrubber_box)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        buttons.pack_start(Gtk.Box(), True, True, 0)

        # Repeat button
        self.repeat_button = util.button_with_icon('media-playlist-repeat')
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
        self.shuffle_button = util.button_with_icon('media-playlist-shuffle')
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
        up_next_button = util.button_with_icon(
            'view-list-symbolic', icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        up_next_button.connect('clicked', self.on_up_next_click)
        box.pack_start(up_next_button, False, True, 5)

        self.up_next_popover = Gtk.PopoverMenu(name='up-next-popover')

        popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        popover_box_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.popover_label = Gtk.Label(
            label='<b>Up Next</b>',
            use_markup=True,
            halign=Gtk.Align.START,
            margin=10,
        )
        popover_box_header.add(self.popover_label)

        load_up_next = Gtk.Button(label='Load Queue from Server', margin=5)
        load_up_next.set_action_name('app.update-play-queue-from-server')
        popover_box_header.pack_end(load_up_next, False, False, 0)

        popover_box.add(popover_box_header)

        popover_scroll_box = Gtk.ScrolledWindow(
            min_content_height=600,
            min_content_width=400,
        )
        self.popover_list = Gtk.ListBox()
        popover_scroll_box.add(self.popover_list)
        popover_box.pack_end(popover_scroll_box, True, True, 0)

        self.up_next_popover.add(popover_box)

        # Volume mute toggle
        self.volume_mute_toggle = util.button_with_icon('audio-volume-high')
        self.volume_mute_toggle.set_action_name('app.mute-toggle')
        box.pack_start(self.volume_mute_toggle, False, True, 0)

        # Volume slider
        self.volume_slider = Gtk.Scale.new_with_range(
            orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=5)
        self.volume_slider.set_name('volume-slider')
        self.volume_slider.set_draw_value(False)
        box.pack_start(self.volume_slider, True, True, 0)

        vbox.pack_start(box, False, True, 0)
        vbox.pack_start(Gtk.Box(), True, True, 0)
        return vbox
