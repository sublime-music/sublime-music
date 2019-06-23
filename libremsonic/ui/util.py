import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk


def button_with_icon(
        icon_name,
        relief=False,
        icon_size=Gtk.IconSize.BUTTON,
) -> Gtk.Button:
    button = Gtk.Button()
    icon = Gio.ThemedIcon(name=icon_name)
    image = Gtk.Image.new_from_gicon(icon, icon_size)
    button.add(image)

    if not relief:
        button.props.relief = Gtk.ReliefStyle.NONE

    return button


def format_song_duration(duration_secs) -> str:
    return f'{duration_secs // 60}:{duration_secs % 60:02}'
