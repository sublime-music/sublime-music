import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from .common.edit_form_dialog import EditFormDialog


class SettingsDialog(EditFormDialog):
    title: str = 'Settings'
    initial_size = (450, 250)
    text_fields = [
        (
            'Port Number (for streaming to Chromecasts on the LAN) *',
            'port_number',
            False,
        ),
    ]
    boolean_fields = [
        ('Always stream songs', 'always_stream'),
        ('When streaming, also download song', 'download_on_stream'),
        (
            'Show a notification when a song begins to play',
            'song_play_notification',
        ),
        (
            'Serve locally cached files over the LAN to Chromecast devices. *',
            'serve_over_lan',
        ),
    ]
    numeric_fields = [
        (
            'How many songs in the play queue do you want to prefetch?',
            'prefetch_amount',
            (0, 10, 1),
            0,
        ),
        (
            'How many song downloads do you want to allow concurrently?',
            'concurrent_download_limit',
            (1, 10, 1),
            5,
        ),
    ]
    option_fields = [
        ('Replay Gain', 'replay_gain', ('Disabled', 'Track', 'Album')),
    ]

    def __init__(self, *args, **kwargs):
        self.extra_label = Gtk.Label(
            label='<i>* Will be appplied after restarting Sublime Music</i>',
            justify=Gtk.Justification.LEFT,
            use_markup=True,
        )

        super().__init__(*args, **kwargs)
