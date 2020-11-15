import functools
import logging
import re
from collections import defaultdict
from datetime import timedelta
from typing import Any, Callable, DefaultDict, Dict, List, Match, Optional, Tuple

from deepdiff import DeepDiff
from gi.repository import Gio, GLib

from ..adapters import AdapterManager, CacheMissError
from ..config import AppConfiguration
from ..players import PlayerManager
from ..ui.state import RepeatType
from ..util import resolve_path


def dbus_propagate(param_self: Any = None) -> Callable:
    """Wraps a function which causes changes to DBus properties."""

    def decorator(function: Callable) -> Callable:
        @functools.wraps(function)
        def wrapper(*args):
            function(*args)
            if (param_self or args[0]).dbus_manager:
                (param_self or args[0]).dbus_manager.property_diff()

        return wrapper

    return decorator


class DBusManager:
    second_microsecond_conversion = 1000000

    current_state: Dict = {}

    def __init__(
        self,
        connection: Gio.DBusConnection,
        do_on_method_call: Callable[
            [
                Gio.DBusConnection,
                str,
                str,
                str,
                str,
                GLib.Variant,
                Gio.DBusMethodInvocation,
            ],
            None,
        ],
        on_set_property: Callable[
            [Gio.DBusConnection, str, str, str, str, GLib.Variant], None
        ],
        get_config_and_player_manager: Callable[
            [], Tuple[AppConfiguration, Optional[PlayerManager]]
        ],
    ):
        self.get_config_and_player_manager = get_config_and_player_manager
        self.do_on_method_call = do_on_method_call
        self.on_set_property = on_set_property
        self.connection = connection

        def dbus_name_acquired(connection: Gio.DBusConnection, name: str):
            specs = [
                "org.mpris.MediaPlayer2.xml",
                "org.mpris.MediaPlayer2.Player.xml",
                "org.mpris.MediaPlayer2.Playlists.xml",
                "org.mpris.MediaPlayer2.TrackList.xml",
            ]
            for spec in specs:
                spec_path = resolve_path("dbus/mpris_specs", spec)
                with open(spec_path) as f:
                    node_info = Gio.DBusNodeInfo.new_for_xml(f.read())

                connection.register_object(
                    "/org/mpris/MediaPlayer2",
                    node_info.interfaces[0],
                    self.on_method_call,
                    self.on_get_property,
                    self.on_set_property,
                )

        # TODO (#127): I have no idea what to do here.
        def dbus_name_lost(*args):
            pass

        self.bus_number = Gio.bus_own_name_on_connection(
            connection,
            "org.mpris.MediaPlayer2.sublimemusic",
            Gio.BusNameOwnerFlags.NONE,
            dbus_name_acquired,
            dbus_name_lost,
        )

    def shutdown(self):
        logging.info("DBusManager is shutting down.")
        self.property_diff()
        Gio.bus_unown_name(self.bus_number)

    def on_get_property(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        path: str,
        interface: str,
        property_name: str,
    ) -> GLib.Variant:
        value = self.property_dict().get(interface, {}).get(property_name)
        return DBusManager.to_variant(value)

    def on_method_call(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        path: str,
        interface: str,
        method: str,
        params: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ):
        # TODO (#127): I don't really know if this works.
        if interface == "org.freedesktop.DBus.Properties":
            if method == "Get":
                invocation.return_value(
                    self.on_get_property(connection, sender, path, interface, *params)
                )
            elif method == "Set":
                self.on_set_property(connection, sender, path, interface, *params)
            elif method == "GetAll":
                all_properties = {
                    k: DBusManager.to_variant(v)
                    for k, v in self.property_dict()[interface].items()
                }
                invocation.return_value(GLib.Variant("(a{sv})", (all_properties,)))

            return
        self.do_on_method_call(
            connection,
            sender,
            path,
            interface,
            method,
            params,
            invocation,
        )

    @staticmethod
    def to_variant(value: Any) -> GLib.Variant:
        if callable(value):
            return DBusManager.to_variant(value())

        if isinstance(value, GLib.Variant):
            return value

        if type(value) == tuple:
            return GLib.Variant(*value)

        if type(value) == dict:
            return GLib.Variant(
                "a{sv}",
                {k: DBusManager.to_variant(v) for k, v in value.items()},
            )

        variant_type = {list: "as", str: "s", int: "i", float: "d", bool: "b"}.get(
            type(value)
        )
        if not variant_type:
            return value
        return GLib.Variant(variant_type, value)

    _escape_re = re.compile(r"[^\w]+")

    @staticmethod
    @functools.lru_cache(maxsize=1024)
    def _escape_id(id: str) -> str:
        """
        Escapes an ID for use in a DBus object identifier.

        >>> DBusManager._escape_id("tr-1843")
        'tr_0x45_1843'
        >>> DBusManager._escape_id("bc9c7726-8739-4add-8df0-88c6233f37df")
        'bc9c7726_0x45_8739_0x45_4add_0x45_8df0_0x45_88c6233f37df'
        >>> DBusManager._escape_id("spaces spaces everywhere")
        'spaces_0x32_spaces_0x32_everywhere'
        >>> DBusManager._escape_id("already/has/slashes")
        'already_0x47_has_0x47_slashes'
        """

        def replace(m: Match[str]) -> str:
            return f"_0x{ord(m[0])}_"

        return DBusManager._escape_re.sub(replace, id)

    def property_dict(self) -> Dict[str, Any]:
        config, player_manager = self.get_config_and_player_manager()
        if config is None or player_manager is None:
            return {}

        state = config.state
        has_current_song = state.current_song is not None
        has_next_song = False
        if state.repeat_type in (RepeatType.REPEAT_QUEUE, RepeatType.REPEAT_SONG):
            has_next_song = True
        elif has_current_song:
            has_next_song = state.current_song_index < len(state.play_queue) - 1

        active_playlist = self.get_active_playlist(state.active_playlist_id)

        playlist_count = 0
        try:
            get_playlists_result = AdapterManager.get_playlists(allow_download=False)
            if get_playlists_result.data_is_available:
                playlist_count = len(get_playlists_result.result())
        except Exception:
            pass

        return {
            "org.mpris.MediaPlayer2": {
                "CanQuit": True,
                "CanRaise": True,
                "HasTrackList": True,
                "Identity": "Sublime Music",
                "DesktopEntry": "sublime-music",
                "SupportedUriSchemes": [],
                "SupportedMimeTypes": [],
            },
            "org.mpris.MediaPlayer2.Player": {
                "PlaybackStatus": {
                    (False, False): "Stopped",
                    (False, True): "Stopped",
                    (True, False): "Paused",
                    (True, True): "Playing",
                }[player_manager.song_loaded, state.playing],
                "LoopStatus": state.repeat_type.as_mpris_loop_status(),
                "Rate": 1.0,
                "Shuffle": state.shuffle_on,
                "Metadata": self.get_mpris_metadata(
                    state.current_song_index,
                    state.play_queue,
                )
                if state.current_song
                else {},
                "Volume": 0.0 if state.is_muted else state.volume / 100,
                "Position": (
                    "x",
                    int(
                        max(state.song_progress.total_seconds(), 0)
                        * self.second_microsecond_conversion
                    ),
                ),
                "MinimumRate": 1.0,
                "MaximumRate": 1.0,
                "CanGoNext": has_current_song and has_next_song,
                "CanGoPrevious": has_current_song,
                "CanPlay": True,
                "CanPause": True,
                "CanSeek": True,
                "CanControl": True,
            },
            "org.mpris.MediaPlayer2.TrackList": {
                "Tracks": DBusManager.get_dbus_playlist(state.play_queue),
                "CanEditTracks": False,
            },
            "org.mpris.MediaPlayer2.Playlists": {
                "PlaylistCount": playlist_count,
                "Orderings": ["Alphabetical", "Created", "Modified"],
                "ActivePlaylist": ("(b(oss))", active_playlist),
            },
        }

    @functools.lru_cache(maxsize=10)
    def get_active_playlist(
        self, active_playlist_id: Optional[str]
    ) -> Tuple[bool, GLib.Variant]:
        if not active_playlist_id or not AdapterManager.can_get_playlist_details():
            return (False, GLib.Variant("(oss)", ("/", "", "")))

        try:
            playlist = AdapterManager.get_playlist_details(
                active_playlist_id, allow_download=False
            ).result()

            try:
                cover_art = AdapterManager.get_cover_art_uri(
                    playlist.cover_art, "file", allow_download=False
                ).result()
            except CacheMissError:
                cover_art = ""

            return (
                True,
                GLib.Variant(
                    "(oss)",
                    (
                        "/playlist/" + DBusManager._escape_id(playlist.id),
                        playlist.name,
                        cover_art,
                    ),
                ),
            )
        except Exception:
            logging.exception("Couldn't get playlist details")
            return (False, GLib.Variant("(oss)", ("/", "", "")))

    @functools.lru_cache(maxsize=10)
    def get_mpris_metadata(
        self, idx: int, play_queue: Tuple[str, ...]
    ) -> Dict[str, Any]:
        try:
            song = AdapterManager.get_song_details(
                play_queue[idx], allow_download=False
            ).result()
        except Exception:
            return {}

        trackid = DBusManager.get_dbus_playlist(play_queue)[idx]
        duration = (
            "x",
            int(
                (song.duration or timedelta(0)).total_seconds()
                * self.second_microsecond_conversion
            ),
        )

        try:
            cover_art = AdapterManager.get_cover_art_uri(
                song.cover_art, "file", allow_download=False
            ).result()
            cover_art = "file://" + cover_art
        except CacheMissError:
            cover_art = ""

        artist_name = song.artist.name if song.artist else ""
        return {
            "mpris:trackid": trackid,
            "mpris:length": duration,
            # Art URIs should be sent as (UTF-8) strings.
            # Local files should use the "file://" schema.
            "mpris:artUrl": cover_art,
            # TODO (#71) use walrus once MYPY isn't retarded
            "xesam:album": (song.album.name if song.album else ""),
            "xesam:albumArtist": [artist_name],
            "xesam:artist": [artist_name],
            "xesam:title": song.title,
        }

    @staticmethod
    @functools.lru_cache(maxsize=20)
    def get_dbus_playlist(play_queue: Tuple[str, ...]) -> List[str]:
        """
        Gets a playlist formatted for DBus. If multiples of the same element exist in
        the queue, it will use ``/0`` after the song ID to differentiate between the
        instances.

        >>> DBusManager.get_dbus_playlist(("2", "1", "3", "1"))
        ['/song/2/0', '/song/1/0', '/song/3/0', '/song/1/1']
        """
        seen_counts: DefaultDict[str, int] = defaultdict(int)
        tracks = []
        for song_id in play_queue:
            num_seen = seen_counts[song_id]
            tracks.append(f"/song/{DBusManager._escape_id(song_id)}/{num_seen}")
            seen_counts[song_id] += 1

        return tracks

    diff_parse_re = re.compile(r"root\['(.*?)'\]\['(.*?)'\](?:\[.*\])?")

    def property_diff(self):
        new_property_dict = self.property_dict()
        diff = DeepDiff(self.current_state, new_property_dict)

        changes = defaultdict(dict)

        for path, change in diff.get("values_changed", {}).items():
            interface, property_name = self.diff_parse_re.match(path).groups()
            changes[interface][property_name] = change["new_value"]

        if diff.get("dictionary_item_added"):
            changes = new_property_dict

        for interface, changed_props in changes.items():
            # If the metadata has changed, just make the entire Metadata object
            # part of the update.
            if "Metadata" in changed_props.keys():
                changed_props["Metadata"] = new_property_dict[interface]["Metadata"]

            # Special handling for when the position changes (a seek).
            # Technically, I'm sending this signal too often, but I don't think
            # it really matters.
            if (
                interface == "org.mpris.MediaPlayer2.Player"
                and "Position" in changed_props
            ):
                self.connection.emit_signal(
                    None,
                    "/org/mpris/MediaPlayer2",
                    interface,
                    "Seeked",
                    GLib.Variant("(x)", (changed_props["Position"][1],)),
                )

                # Do not emit the property change.
                del changed_props["Position"]

            # Special handling for when the track list changes.
            # Technically, I'm supposed to use `TrackAdded` and `TrackRemoved`
            # signals when minor changes occur, but the docs also say that:
            #
            # > It is left up to the implementation to decide when a change to
            # > the track list is invasive enough that this signal should be
            # > emitted instead of a series of TrackAdded and TrackRemoved
            # > signals.
            #
            # So I think that any change is invasive enough that I should use
            # this signal.
            if (
                interface == "org.mpris.MediaPlayer2.TrackList"
                and "Tracks" in changed_props
            ):
                track_list = changed_props["Tracks"]
                if len(track_list) > 0:
                    current_track = new_property_dict["org.mpris.MediaPlayer2.Player"][
                        "Metadata"
                    ].get("mpris:trackid", track_list[0])
                    self.connection.emit_signal(
                        None,
                        "/org/mpris/MediaPlayer2",
                        interface,
                        "TrackListReplaced",
                        GLib.Variant("(aoo)", (track_list, current_track)),
                    )

            self.connection.emit_signal(
                None,
                "/org/mpris/MediaPlayer2",
                "org.freedesktop.DBus.Properties",
                "PropertiesChanged",
                GLib.Variant(
                    "(sa{sv}as)",
                    (
                        interface,
                        {
                            k: DBusManager.to_variant(v)
                            for k, v in changed_props.items()
                        },
                        [],
                    ),
                ),
            )

        # Update state for next diff.
        self.current_state = new_property_dict
