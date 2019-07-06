import functools
from typing import Callable, List, Tuple, Any, Optional

from concurrent.futures import Future

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, GObject, GLib, Gdk

from libremsonic.cache_manager import CacheManager, SongCacheStatus


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


def format_sequence_duration(duration_secs) -> str:
    duration_mins = (duration_secs // 60) % 60
    duration_hrs = duration_secs // 60 // 60
    duration_secs = duration_secs % 60

    format_components = []
    if duration_hrs > 0:
        hrs = '{} {}'.format(duration_hrs, pluralize('hour', duration_hrs))
        format_components.append(hrs)

    if duration_mins > 0:
        mins = '{} {}'.format(duration_mins, pluralize('minute',
                                                       duration_mins))
        format_components.append(mins)

    # Show seconds if there are no hours.
    if duration_hrs == 0:
        secs = '{} {}'.format(duration_secs, pluralize('second',
                                                       duration_secs))
        format_components.append(secs)

    return ', '.join(format_components)


def esc(string):
    return string.replace('&', '&amp;').replace(" target='_blank'", '')


def dot_join(*items):
    return '  •  '.join(map(str, items))


def show_song_popover(
        song_ids,
        x: int,
        y: int,
        relative_to: Any,
        position: Gtk.PositionType = Gtk.PositionType.BOTTOM,
        on_download_state_change: Callable[[int], None] = lambda x: None,
        show_remove_from_playlist_button: bool = False,
        extra_menu_items: List[Tuple[Gtk.ModelButton, Any]] = [],
):
    def on_download_songs_click(button):
        CacheManager.batch_download_songs(
            song_ids,
            before_download=on_download_state_change,
            on_song_download_complete=on_download_state_change,
        )

    def on_add_to_playlist_click(button, playlist):
        CacheManager.executor.submit(
            CacheManager.update_playlist,
            playlist_id=playlist.id,
            song_id_to_add=song_ids,
        )

    popover = Gtk.PopoverMenu()
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

    # Add all of the menu items to the popover.
    song_count = len(song_ids)

    # Determine if we should enable the download button.
    sensitive = False
    for song_id in song_ids:
        details = CacheManager.get_song_details(song_id)
        status = CacheManager.get_cached_status(details.result())
        if status == SongCacheStatus.NOT_CACHED:
            sensitive = True
            break

    menu_items = [
        (Gtk.ModelButton(text='Add to up next'), None),
        (Gtk.ModelButton(text='Add to queue'), None),
        (Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), None),
        (Gtk.ModelButton(text='Go to album'), None),
        (Gtk.ModelButton(text='Go to artist'), None),
        (Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), None),
        (
            Gtk.ModelButton(
                text=(f"Download {pluralize('song', song_count)}"
                      if song_count > 1 else 'Download Song'),
                sensitive=sensitive,
            ),
            on_download_songs_click,
        ),
        (Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), None),
        (
            Gtk.ModelButton(
                text=f"Add {pluralize('song', song_count)} to playlist",
                menu_name='add-to-playlist',
            ),
            None,
        ),
        *extra_menu_items,
    ]

    for item, action in menu_items:
        if action:
            item.connect('clicked', action)
        if type(item) == Gtk.ModelButton:
            item.get_style_context().add_class('menu-button')
        vbox.pack_start(item, False, True, 0)

    popover.add(vbox)

    # Create the "Add song(s) to playlist" sub-menu.
    playlists_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

    # Back button
    playlists_vbox.add(
        Gtk.ModelButton(
            inverted=True,
            centered=True,
            menu_name='main',
        ))

    # The playlist buttons
    for playlist in CacheManager.get_playlists().result():
        button = Gtk.ModelButton(text=playlist.name)
        button.get_style_context().add_class('menu-button')
        button.connect('clicked', on_add_to_playlist_click, playlist)
        playlists_vbox.pack_start(button, False, True, 0)

    popover.add(playlists_vbox)
    popover.child_set_property(playlists_vbox, 'submenu', 'add-to-playlist')

    # Positioning of the popover.
    rect = Gdk.Rectangle()
    rect.x, rect.y, rect.width, rect.height = x, y, 1, 1
    popover.set_pointing_to(rect)
    popover.set_position(position)
    popover.set_relative_to(relative_to)

    popover.popup()
    popover.show_all()


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
