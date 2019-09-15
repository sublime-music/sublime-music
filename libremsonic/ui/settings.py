import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject

from .common.edit_form_dialog import EditFormDialog


class SettingsDialog(EditFormDialog):
    title: str = 'Settings'
    initial_size = (450, 250)
    text_fields = [
        ('Port Number (will take effect on restart)', 'port_number', False),
    ]
    boolean_fields = [
        ('Show headers on song lists', 'show_headers'),
        ('Always stream songs', 'always_stream'),
        ('When streaming, also download song', 'download_on_stream'),
        (
            'Show a notification when a song begins to play',
            'song_play_notification',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
