import functools
import re
from datetime import timedelta
from typing import (
    Any,
    Callable,
    cast,
    Iterable,
    List,
    Match,
    Optional,
    Tuple,
    Union,
)

from deepdiff import DeepDiff
from gi.repository import Gdk, GLib, Gtk

from sublime.adapters import AdapterManager, Result, SongCacheStatus
from sublime.adapters.api_objects import Playlist, Song
from sublime.config import AppConfiguration


def format_song_duration(duration_secs: Union[int, timedelta, None]) -> str:
    """
    Formats the song duration as mins:seconds with the seconds being
    zero-padded if necessary.

    >>> format_song_duration(80)
    '1:20'
    >>> format_song_duration(62)
    '1:02'
    >>> format_song_duration(timedelta(seconds=68.2))
    '1:08'
    >>> format_song_duration(None)
    '-:--'
    """
    if isinstance(duration_secs, timedelta):
        duration_secs = round(duration_secs.total_seconds())
    if duration_secs is None:
        return "-:--"

    duration_secs = max(duration_secs, 0)

    return f"{duration_secs // 60}:{duration_secs % 60:02}"


def pluralize(string: str, number: int, pluralized_form: str = None,) -> str:
    """
    Pluralize the given string given the count as a number.

    >>> pluralize('foo', 1)
    'foo'
    >>> pluralize('foo', 2)
    'foos'
    >>> pluralize('foo', 0)
    'foos'
    """
    if number != 1:
        return pluralized_form or f"{string}s"
    return string


def format_sequence_duration(duration: Optional[timedelta]) -> str:
    """
    Formats duration in English.

    >>> format_sequence_duration(timedelta(seconds=90))
    '1 minute, 30 seconds'
    >>> format_sequence_duration(seconds=(60 * 60 + 120))
    '1 hour, 2 minutes'
    >>> format_sequence_duration(None)
    '0 seconds'
    """
    duration_secs = round(duration.total_seconds()) if duration else 0
    duration_mins = (duration_secs // 60) % 60
    duration_hrs = duration_secs // 60 // 60
    duration_secs = duration_secs % 60

    format_components = []
    if duration_hrs > 0:
        hrs = "{} {}".format(duration_hrs, pluralize("hour", duration_hrs))
        format_components.append(hrs)

    if duration_mins > 0:
        mins = "{} {}".format(duration_mins, pluralize("minute", duration_mins))
        format_components.append(mins)

    # Show seconds if there are no hours.
    if duration_hrs == 0:
        secs = "{} {}".format(duration_secs, pluralize("second", duration_secs))
        format_components.append(secs)

    return ", ".join(format_components)


def esc(string: Optional[str]) -> str:
    """
    >>> esc("test & <a href='ohea' target='_blank'>test</a>")
    "test &amp; <a href='ohea'>test</a>"
    >>> esc(None)
    ''
    """
    if string is None:
        return ""
    return string.replace("&", "&amp;").replace(" target='_blank'", "")


def dot_join(*items: Any) -> str:
    """
    Joins the given strings with a dot character. Filters out ``None`` values.

    >>> dot_join(None, "foo", "bar", None, "baz")
    'foo  •  bar  •  baz'
    """
    return "  •  ".join(map(str, filter(lambda x: x is not None, items)))


def get_cached_status_icons(songs: List[Song]) -> List[str]:
    cache_icon = {
        SongCacheStatus.CACHED: "folder-download-symbolic",
        SongCacheStatus.PERMANENTLY_CACHED: "view-pin-symbolic",
        SongCacheStatus.DOWNLOADING: "emblem-synchronizing-symbolic",
    }
    return [
        cache_icon.get(cache_status, "")
        for cache_status in AdapterManager.get_cached_statuses(songs)
    ]


def _parse_diff_location(location: str) -> Tuple:
    """
    Parses a diff location as returned by deepdiff.

    >>> _parse_diff_location("root[22]")
    ('22',)
    >>> _parse_diff_location("root[22][4]")
    ('22', '4')
    >>> _parse_diff_location("root[22].foo")
    ('22', 'foo')
    """
    match = re.match(r"root\[(\d*)\](?:\[(\d*)\]|\.(.*))?", location)
    return tuple(g for g in cast(Match, match).groups() if g is not None)


def diff_song_store(store_to_edit: Any, new_store: Iterable[Any]):
    """
    Diffing song stores is nice, because we can easily make edits by modifying
    the underlying store.
    """
    old_store = [row[:] for row in store_to_edit]

    # Diff the lists to determine what needs to be changed.
    diff = DeepDiff(old_store, new_store)
    changed = diff.get("values_changed", {})
    added = diff.get("iterable_item_added", {})
    removed = diff.get("iterable_item_removed", {})

    for edit_location, diff in changed.items():
        idx, field = _parse_diff_location(edit_location)
        store_to_edit[int(idx)][int(field)] = diff["new_value"]

    for _, value in added.items():
        store_to_edit.append(value)

    for remove_location, _ in reversed(list(removed.items())):
        remove_at = int(_parse_diff_location(remove_location)[0])
        del store_to_edit[remove_at]


def diff_model_store(store_to_edit: Any, new_store: Iterable[Any]):
    """
    The diff here is that if there are any differences, then we refresh the
    entire list. This is because it is too hard to do editing.
    """
    # TODO: figure out if there's a way to do editing.
    old_store = store_to_edit[:]

    diff = DeepDiff(old_store, new_store)
    if diff == {}:
        return

    store_to_edit.splice(0, len(store_to_edit), new_store)


def show_song_popover(
    song_ids: List[str],
    x: int,
    y: int,
    relative_to: Any,
    position: Gtk.PositionType = Gtk.PositionType.BOTTOM,
    on_download_state_change: Callable[[str], None] = lambda _: None,
    show_remove_from_playlist_button: bool = False,
    extra_menu_items: List[Tuple[Gtk.ModelButton, Any]] = None,
):
    def on_download_songs_click(_: Any):
        AdapterManager.batch_download_songs(
            song_ids,
            before_download=on_download_state_change,
            on_song_download_complete=on_download_state_change,
        )

    def on_remove_downloads_click(_: Any):
        AdapterManager.batch_delete_cached_songs(
            song_ids, on_song_delete=on_download_state_change,
        )

    def on_add_to_playlist_click(_: Any, playlist: Playlist):
        AdapterManager.update_playlist(
            playlist_id=playlist.id, append_song_ids=song_ids
        )
        # TODO: make this update the entire window (or at least what's visible)

    popover = Gtk.PopoverMenu()
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

    # Add all of the menu items to the popover.
    song_count = len(song_ids)

    # Determine if we should enable the download button.
    download_sensitive, remove_download_sensitive = False, False
    albums, artists, parents = set(), set(), set()
    # TODO lazy load these
    song_details = [
        AdapterManager.get_song_details(song_id).result() for song_id in song_ids
    ]
    song_cache_statuses = AdapterManager.get_cached_statuses(song_details)
    for song, status in zip(song_details, song_cache_statuses):
        # TODO lazy load these
        albums.add(album.id if (album := song.album) else None)
        artists.add(artist.id if (artist := song.artist) else None)
        parents.add(parent_id if (parent_id := song.parent_id) else None)

        download_sensitive |= status == SongCacheStatus.NOT_CACHED
        remove_download_sensitive |= status in (
            SongCacheStatus.CACHED,
            SongCacheStatus.PERMANENTLY_CACHED,
        )

    go_to_album_button = Gtk.ModelButton(
        text="Go to album", action_name="app.go-to-album"
    )
    if len(albums) == 1 and list(albums)[0] is not None:
        album_value = GLib.Variant("s", list(albums)[0])
        go_to_album_button.set_action_target_value(album_value)

    go_to_artist_button = Gtk.ModelButton(
        text="Go to artist", action_name="app.go-to-artist"
    )
    if len(artists) == 1 and list(artists)[0] is not None:
        artist_value = GLib.Variant("s", list(artists)[0])
        go_to_artist_button.set_action_target_value(artist_value)

    browse_to_song = Gtk.ModelButton(
        text=f"Browse to {pluralize('song', song_count)}", action_name="app.browse-to",
    )
    if len(parents) == 1 and list(parents)[0] is not None:
        parent_value = GLib.Variant("s", list(parents)[0])
        browse_to_song.set_action_target_value(parent_value)

    menu_items = [
        Gtk.ModelButton(
            text="Play next",
            action_name="app.play-next",
            action_target=GLib.Variant("as", song_ids),
        ),
        Gtk.ModelButton(
            text="Add to queue",
            action_name="app.add-to-queue",
            action_target=GLib.Variant("as", song_ids),
        ),
        Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
        go_to_album_button,
        go_to_artist_button,
        browse_to_song,
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
            menu_name="add-to-playlist",
        ),
        *(extra_menu_items or []),
    ]

    for item in menu_items:
        if type(item) == tuple:
            el, fn = item
            el.connect("clicked", fn)
            el.get_style_context().add_class("menu-button")
            vbox.pack_start(item[0], False, True, 0)
        else:
            item.get_style_context().add_class("menu-button")
            vbox.pack_start(item, False, True, 0)

    popover.add(vbox)

    # Create the "Add song(s) to playlist" sub-menu.
    playlists_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

    # Back button
    playlists_vbox.add(Gtk.ModelButton(inverted=True, centered=True, menu_name="main",))

    # The playlist buttons
    # TODO lazy load
    for playlist in AdapterManager.get_playlists().result():
        button = Gtk.ModelButton(text=playlist.name)
        button.get_style_context().add_class("menu-button")
        button.connect("clicked", on_add_to_playlist_click, playlist)
        playlists_vbox.pack_start(button, False, True, 0)

    popover.add(playlists_vbox)
    popover.child_set_property(playlists_vbox, "submenu", "add-to-playlist")

    # Positioning of the popover.
    rect = Gdk.Rectangle()
    rect.x, rect.y, rect.width, rect.height = x, y, 1, 1
    popover.set_pointing_to(rect)
    popover.set_position(position)
    popover.set_relative_to(relative_to)

    popover.popup()
    popover.show_all()


def async_callback(
    future_fn: Callable[..., Result],
    before_download: Callable[[Any], None] = None,
    on_failure: Callable[[Any, Exception], None] = None,
) -> Callable[[Callable], Callable]:
    """
    Defines the ``async_callback`` decorator.

    When a function is annotated with this decorator, the function becomes the done
    callback for the given result-generating lambda function. The annotated function
    will be called with the result of the Result generated by said lambda function.

    :param future_fn: a function which generates an :class:`AdapterManager.Result`.
    """

    def decorator(callback_fn: Callable) -> Callable:
        @functools.wraps(callback_fn)
        def wrapper(
            self: Any,
            *args,
            app_config: AppConfiguration = None,
            force: bool = False,
            order_token: int = None,
            **kwargs,
        ):
            def on_before_download():
                if before_download:
                    GLib.idle_add(before_download, self)

            def future_callback(is_immediate: bool, f: Result):
                try:
                    result = f.result()
                except Exception as e:
                    if on_failure:
                        GLib.idle_add(on_failure, self, e)
                    return

                fn = functools.partial(
                    callback_fn,
                    self,
                    result,
                    app_config=app_config,
                    force=force,
                    order_token=order_token,
                )

                if is_immediate:
                    # The data is available now, no need to wait for the future to
                    # finish, and no need to incur the overhead of adding to the GLib
                    # event queue.
                    fn()
                else:
                    # We don'h have the data, and we have to idle add so that we don't
                    # seg fault GTK.
                    GLib.idle_add(fn)

            result: Result = future_fn(
                *args, before_download=on_before_download, force=force, **kwargs,
            )
            result.add_done_callback(
                functools.partial(future_callback, result.data_is_available)
            )

        return wrapper

    return decorator
