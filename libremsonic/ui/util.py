import gi
import functools

from concurrent.futures import Future

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, GObject, GLib


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


def async_callback(future_fn, before_download=None, on_failure=None):
    """
    Defines the ``async_callback`` decorator.

    When a function is annotated with this decorator, the function becomes the
    done callback for the given future-generating lambda function. The
    annotated function will be called with the result of the future generated
    by said lambda function.

    :param future_fn: a function which generates a
        ``concurrent.futures.Future``.
    """

    def decorator(callback_fn):
        @functools.wraps(callback_fn)
        def wrapper(self, *args, **kwargs):
            if before_download:
                on_before_download = (
                    lambda: GLib.idle_add(before_download, self))
            else:
                on_before_download = (lambda: None)

            def future_callback(f):
                try:
                    result = f.result()
                except Exception as e:
                    if on_failure:
                        on_failure(self, e)
                    return

                return GLib.idle_add(callback_fn, self, result)

            future: Future = future_fn(
                *args,
                before_download=on_before_download,
                **kwargs,
            )
            future.add_done_callback(future_callback)

        return wrapper

    return decorator
