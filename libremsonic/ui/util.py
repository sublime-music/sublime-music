import functools
from typing import List, Tuple

from concurrent.futures import Future

import gi
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


def pluralize(string: str, number: int, pluralized_form=None):
    if number != 1:
        return pluralized_form or f'{string}s'
    return string


def esc(string):
    return string.replace('&', '&amp;')


class EditFormDialog(Gtk.Dialog):
    entity_name: str
    initial_size: Tuple[int, int]
    text_fields: List[Tuple[str, str, bool]] = []
    boolean_fields: List[Tuple[str, str]] = []
    extra_buttons: List[Gtk.Button] = []

    def get_object_name(self, obj):
        """
        Gets the friendly object name. Can be overridden.
        """
        return obj.name if obj else ''

    def get_default_object(self):
        return None

    def __init__(self, parent, existing_object=None):
        editing = existing_object is not None
        Gtk.Dialog.__init__(
            self,
            f'Edit {self.get_object_name(existing_object)}'
            if editing else f'Create New {self.entity_name}',
            parent,
            0,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_EDIT if editing else Gtk.STOCK_ADD,
             Gtk.ResponseType.OK),
        )

        if not existing_object:
            existing_object = self.get_default_object()

        self.set_default_size(*self.initial_size)

        if len(self.text_fields) + len(self.boolean_fields) > 0:
            # Create two columns for the labels and corresponding entry fields.
            content_area = self.get_content_area()
            flowbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            flowbox.pack_start(label_box, False, True, 10)
            flowbox.pack_start(entry_box, True, True, 10)

            # Store a map of field label to GTK component.
            self.data = {}

            # Create all of the text entry fields.
            for label, value_field_name, is_password in self.text_fields:
                # Put the label in the left box.
                entry_label = Gtk.Label(label=label + ':')
                entry_label.set_halign(Gtk.Align.START)
                label_box.pack_start(entry_label, True, True, 0)

                # Put the text entry in the right box.
                entry = Gtk.Entry(
                    text=getattr(existing_object, value_field_name, ''))
                if is_password:
                    entry.set_visibility(False)
                entry_box.pack_start(entry, True, True, 0)
                self.data[label] = entry

            # Create all of the check box fields.
            for label, value_field_name in self.boolean_fields:
                # Put the label in the left box.
                entry_label = Gtk.Label(label=label + ':')
                entry_label.set_halign(Gtk.Align.START)
                label_box.pack_start(entry_label, True, True, 0)

                # Put the checkbox in the right box. Note we have to pad here
                # since the checkboxes are smaller than the text fields.
                checkbox = Gtk.CheckButton(
                    active=getattr(existing_object, value_field_name, False))
                entry_box.pack_start(checkbox, True, True, 5)
                self.data[label] = checkbox

            content_area.pack_start(flowbox, True, True, 10)

        # Create a box for buttons.
        if len(self.extra_buttons) > 0:
            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            for button in self.extra_buttons:
                button_box.pack_start(button, False, True, 5)
            content_area.pack_start(button_box, True, True, 10)

        self.show_all()


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
