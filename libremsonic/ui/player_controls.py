import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, Gtk

from libremsonic.state_manager import ApplicationState


class PlayerControls(Gtk.ActionBar):
    """
    Defines the player controls panel that appears at the bottom of the window.
    """

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

    def create_song_display(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.album_art = Gtk.Image()
        box.pack_start(self.album_art, False, False, 5)

        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        details_box.pack_start(Gtk.Box(), True, True, 0)

        self.song_name = Gtk.Label('<b>Song name</b>',
                                   halign=Gtk.Align.START,
                                   use_markup=True)
        self.song_name.set_name('song-name')
        details_box.add(self.song_name)

        self.album_name = Gtk.Label('Album name', halign=Gtk.Align.START)
        self.album_name.set_name('album-name')
        details_box.add(self.album_name)

        self.artist_name = Gtk.Label('<i>Artist name</i>',
                                     halign=Gtk.Align.START,
                                     use_markup=True)
        self.artist_name.set_name('artist-name')
        details_box.add(self.artist_name)

        details_box.pack_start(Gtk.Box(), True, True, 0)
        box.pack_start(details_box, True, True, 5)

        return box

    def create_playback_controls(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Scrubber and song progress/length labels
        scrubber_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.song_progress_label = Gtk.Label('0:00')
        scrubber_box.pack_start(self.song_progress_label, False, False, 5)

        self.song_scrubber = Gtk.Scale.new_with_range(
            orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=5)
        self.song_scrubber.set_name('song-scrubber')
        self.song_scrubber.set_draw_value(False)
        scrubber_box.pack_start(self.song_scrubber, True, True, 0)

        self.song_length_label = Gtk.Label('0:00')
        scrubber_box.pack_start(self.song_length_label, False, False, 5)

        box.add(scrubber_box)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        buttons.pack_start(Gtk.Box(), True, True, 0)

        # Repeat button
        self.repeat_button = self.button_with_icon(
            'media-playlist-repeat-symbolic')
        self.repeat_button.set_action_name('app.repeat-press')
        buttons.pack_start(self.repeat_button, False, False, 5)

        # Previous button
        previous_button = self.button_with_icon(
            'media-skip-backward-symbolic',
            icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        previous_button.set_action_name('app.prev-track')
        buttons.pack_start(previous_button, False, False, 5)

        # Play button
        self.play_button = self.button_with_icon(
            'media-playback-start-symbolic',
            relief=True,
            icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        self.play_button.set_name('play-button')
        self.play_button.set_action_name('app.play-pause')
        buttons.pack_start(self.play_button, False, False, 0)

        # Next button
        next_button = self.button_with_icon(
            'media-skip-forward-symbolic',
            icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        next_button.set_action_name('app.next-track')
        buttons.pack_start(next_button, False, False, 5)

        # Shuffle button
        self.shuffle_button = self.button_with_icon(
            'media-playlist-shuffle-symbolic')
        self.shuffle_button.set_action_name('app.shuffle-press')
        buttons.pack_start(self.shuffle_button, False, False, 5)

        buttons.pack_start(Gtk.Box(), True, True, 0)
        box.add(buttons)

        return box

    def create_up_next_volume(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        # Up Next button
        # TODO connect it to something.
        up_next_button = self.button_with_icon(
            'view-list-symbolic', icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        box.pack_start(up_next_button, False, True, 5)

        # Volume mute toggle
        # TODO connect it to something.
        self.volume_mute_toggle = self.button_with_icon('audio-volume-high')
        box.pack_start(self.volume_mute_toggle, False, True, 0)

        # Volume slider
        # TODO connect it to something.
        volume_slider = Gtk.Scale.new_with_range(
            orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=5)
        volume_slider.set_name('volume-slider')
        volume_slider.set_draw_value(False)
        volume_slider.set_value(100)
        box.pack_start(volume_slider, True, True, 0)

        return box

    def button_with_icon(self,
                         icon_name,
                         relief=False,
                         icon_size=Gtk.IconSize.BUTTON):
        button = Gtk.Button()
        icon = Gio.ThemedIcon(name=icon_name)
        image = Gtk.Image.new_from_gicon(icon, icon_size)
        button.add(image)

        if not relief:
            button.props.relief = Gtk.ReliefStyle.NONE

        return button
