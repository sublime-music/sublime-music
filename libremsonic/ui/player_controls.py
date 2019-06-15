import gi
import sys

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, Gtk


class PlayerControls(Gtk.Box):
    """
    Defines the player controls panel that appears at the bottom of the window.
    """

    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)

        self.song_display = self.create_song_display()
        self.playback_controls = self.create_playback_controls()
        self.up_next_volume = self.create_up_next_volume()

        # TODO this sucks because we can't use GtkCenterBox, so we nee to
        # figure out a different way to make the playback controls centered
        # even if the song_display and up_next_volume are not the same size.
        self.pack_start(self.song_display, False, True, 5)
        self.pack_start(self.playback_controls, True, True, 5)
        self.pack_end(self.up_next_volume, False, True, 5)

    def create_song_display(self):
        return Gtk.Label('The title and album art here')

    def create_playback_controls(self):
        return Gtk.Label('Buttons and scubber')

    def create_up_next_volume(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # TODO use an icon and connect it to something.
        up_next_button = Gtk.Button('Up Next')
        box.pack_start(up_next_button, False, True, 5)

        # TODO volume indicator icon

        # Volume slider
        volume_slider = Gtk.Scale.new_with_range(
            orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=5)
        volume_slider.set_value_pos(Gtk.PositionType.RIGHT)
        volume_slider.set_name('volume-slider')
        box.pack_start(volume_slider, True, True, 0)
        return box
