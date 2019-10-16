import functools
from typing import Callable, List, Tuple, Any
import re

from concurrent.futures import Future

from deepdiff import DeepDiff

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, GObject

from sublime.cache_manager import CacheManager, SongCacheStatus


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
        mins = '{} {}'.format(
            duration_mins, pluralize('minute', duration_mins))
        format_components.append(mins)

    # Show seconds if there are no hours.
    if duration_hrs == 0:
        secs = '{} {}'.format(
            duration_secs, pluralize('second', duration_secs))
        format_components.append(secs)

    return ', '.join(format_components)


def esc(string):
    if string is None:
        return None
    return string.replace('&', '&amp;').replace(" target='_blank'", '')


def dot_join(*items):
    """
    Joins the given strings with a dot character. Filters out None values.
    """
    return '  •  '.join(map(str, filter(lambda x: x is not None, items)))


def get_cached_status_icon(cache_status: SongCacheStatus):
    cache_icon = {
        SongCacheStatus.NOT_CACHED: '',
        SongCacheStatus.CACHED: 'folder-download-symbolic',
        SongCacheStatus.PERMANENTLY_CACHED: 'view-pin-symbolic',
        SongCacheStatus.DOWNLOADING: 'emblem-synchronizing-symbolic',
    }
    return cache_icon[cache_status]


def _parse_diff_location(location):
    match = re.match(r'root\[(\d*)\](?:\[(\d*)\]|\.(.*))?', location)
    return tuple(g for g in match.groups() if g is not None)


def diff_song_store(store_to_edit, new_store):
    """
    Diffing song stores is nice, because we can easily make edits by modifying
    the underlying store.
    """
    old_store = [row[:] for row in store_to_edit]

    # Diff the lists to determine what needs to be changed.
    diff = DeepDiff(old_store, new_store)
    changed = diff.get('values_changed', {})
    added = diff.get('iterable_item_added', {})
    removed = diff.get('iterable_item_removed', {})

    for edit_location, diff in changed.items():
        idx, field = _parse_diff_location(edit_location)
        store_to_edit[int(idx)][int(field)] = diff['new_value']

    for add_location, value in added.items():
        store_to_edit.append(value)

    for remove_location, value in reversed(list(removed.items())):
        remove_at = int(_parse_diff_location(remove_location)[0])
        del store_to_edit[remove_at]


def diff_model_store(store_to_edit, new_store):
    """
    The diff here is that if there are any differences, then we refresh the
    entire list. This is because it is too hard to do editing.
    """
    old_store = store_to_edit[:]

    diff = DeepDiff(old_store, new_store)
    if diff == {}:
        return

    store_to_edit.remove_all()
    for model in new_store:
        store_to_edit.append(model)


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

    def on_remove_downloads_click(button):
        CacheManager.batch_delete_cached_songs(
            song_ids,
            on_song_delete=on_download_state_change,
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
    download_sensitive, remove_download_sensitive = False, False
    albums, artists = set(), set()
    for song_id in song_ids:
        details = CacheManager.get_song_details(song_id).result()
        status = CacheManager.get_cached_status(details)
        albums.add(details.albumId)
        artists.add(details.artistId)

        if download_sensitive or status == SongCacheStatus.NOT_CACHED:
            download_sensitive = True

        if (remove_download_sensitive
                or status in (SongCacheStatus.CACHED,
                              SongCacheStatus.PERMANENTLY_CACHED)):
            remove_download_sensitive = True

    go_to_album_button = Gtk.ModelButton(
        text='Go to album', action_name='app.go-to-album')
    if len(albums) == 1 and list(albums)[0] is not None:
        album_value = GLib.Variant('s', list(albums)[0])
        go_to_album_button.set_action_target_value(album_value)

    go_to_artist_button = Gtk.ModelButton(
        text='Go to artist', action_name='app.go-to-artist')
    if len(artists) == 1 and list(artists)[0] is not None:
        artist_value = GLib.Variant('s', list(artists)[0])
        go_to_artist_button.set_action_target_value(artist_value)

    menu_items = [
        Gtk.ModelButton(
            text='Play next',
            action_name='app.play-next',
            action_target=GLib.Variant('as', song_ids),
        ),
        Gtk.ModelButton(
            text='Add to queue',
            action_name='app.add-to-queue',
            action_target=GLib.Variant('as', song_ids),
        ),
        Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
        go_to_album_button,
        go_to_artist_button,
        Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
        (
            Gtk.ModelButton(
                text=f"Download {pluralize('song', song_count)}",
                sensitive=download_sensitive,
            ),
            on_download_songs_click,
        ),
        (
            Gtk.ModelButton(
                text=f"Remove {pluralize('download', song_count)}",
                sensitive=remove_download_sensitive,
            ),
            on_remove_downloads_click,
        ),
        Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
        Gtk.ModelButton(
            text=f"Add {pluralize('song', song_count)} to playlist",
            menu_name='add-to-playlist',
        ),
        *extra_menu_items,
    ]

    for item in menu_items:
        if type(item) == tuple:
            el, fn = item
            el.connect('clicked', fn)
            el.get_style_context().add_class('menu-button')
            vbox.pack_start(item[0], False, True, 0)
        else:
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


def async_callback(
        future_fn,
        before_download=None,
        on_failure=None,
):
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
        def wrapper(self, *args, state=None, **kwargs):
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

                return GLib.idle_add(callback_fn, self, result, state)

            future: Future = future_fn(
                *args,
                before_download=on_before_download,
                **kwargs,
            )
            future.add_done_callback(future_callback)

        return wrapper

    return decorator
