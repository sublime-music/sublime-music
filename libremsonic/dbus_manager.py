import os
import re

from collections import defaultdict

from deepdiff import DeepDiff
from gi.repository import Gio, GLib

from .state_manager import RepeatType


class DBusManager:
    second_microsecond_conversion = 1000000

    current_state = {}

    def __init__(
            self,
            connection,
            do_on_method_call,
            on_set_property,
            get_state_and_player,
    ):
        self.get_state_and_player = get_state_and_player
        self.do_on_method_call = do_on_method_call
        self.on_set_property = on_set_property
        self.connection = connection

        def dbus_name_acquired(connection, name):
            specs = [
                'org.mpris.MediaPlayer2.xml',
                'org.mpris.MediaPlayer2.Player.xml',
                'org.mpris.MediaPlayer2.Playlists.xml',
                'org.mpris.MediaPlayer2.TrackList.xml',
            ]
            for spec in specs:
                spec_path = os.path.join(
                    os.path.dirname(__file__),
                    f'ui/mpris_specs/{spec}',
                )
                with open(spec_path) as f:
                    node_info = Gio.DBusNodeInfo.new_for_xml(f.read())

                connection.register_object(
                    '/org/mpris/MediaPlayer2',
                    node_info.interfaces[0],
                    self.on_method_call,
                    self.on_get_property,
                    self.on_set_property,
                )

        # TODO: I have no idea what to do here.
        def dbus_name_lost(*args):
            pass

        self.bus_number = Gio.bus_own_name_on_connection(
            connection,
            'org.mpris.MediaPlayer2.libremsonic',
            Gio.BusNameOwnerFlags.NONE,
            dbus_name_acquired,
            dbus_name_lost,
        )

    def shutdown(self):
        Gio.bus_unown_name(self.bus_number)

    def on_get_property(
            self,
            connection,
            sender,
            path,
            interface,
            property_name,
    ):
        return DBusManager.to_variant(
            self.property_dict().get(
                interface,
                {},
            ).get(property_name))

    def on_method_call(
            self,
            connection,
            sender,
            path,
            interface,
            method,
            params,
            invocation,
    ):
        if interface == 'org.freedesktop.DBus.Properties':
            if method == 'Get':
                invocation.return_value(
                    self.on_get_property(
                        connection, sender, path, interface, *params))
            elif method == 'Set':
                self.on_set_property(
                    connection, sender, path, interface, *params)
            elif method == 'GetAll':
                all_properties = {
                    k: DBusManager.to_variant(v)
                    for k, v in self.property_dict()[interface].items()
                }
                invocation.return_value(
                    GLib.Variant('(a{sv})', (all_properties, )))

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
    def to_variant(value):
        if callable(value):
            return DBusManager.to_variant(value())

        if isinstance(value, GLib.Variant):
            return value

        if type(value) == tuple:
            return GLib.Variant(*value)

        if type(value) == dict:
            return GLib.Variant(
                'a{sv}',
                {k: DBusManager.to_variant(v)
                 for k, v in value.items()},
            )

        variant_type = {
            list: 'as',
            str: 's',
            int: 'i',
            float: 'd',
            bool: 'b',
        }.get(type(value))
        if not variant_type:
            return value
        return GLib.Variant(variant_type, value)

    def property_dict(self):
        state, player = self.get_state_and_player()
        has_current_song = state.current_song is not None
        has_next_song = False
        if state.repeat_type in (RepeatType.REPEAT_QUEUE,
                                 RepeatType.REPEAT_SONG):
            has_next_song = True
        elif has_current_song and state.current_song.id in state.play_queue:
            current = state.play_queue.index(state.current_song.id)
            has_next_song = current < len(state.play_queue) - 1

        return {
            'org.mpris.MediaPlayer2': {
                'CanQuit': True,
                'CanRaise': True,
                'HasTrackList': True,
                'Identity': 'Libremsonic',
                # TODO should implement in #29
                'DesktopEntry': 'foo',
                'SupportedUriSchemes': [],
                'SupportedMimeTypes': [],
            },
            'org.mpris.MediaPlayer2.Player': {
                'PlaybackStatus': {
                    (False, False): 'Stopped',
                    (False, True): 'Stopped',
                    (True, False): 'Paused',
                    (True, True): 'Playing',
                }[player.song_loaded, state.playing],
                'LoopStatus':
                state.repeat_type.as_mpris_loop_status(),
                'Rate':
                1.0,
                'Shuffle':
                state.shuffle_on,
                'Metadata': {
                    'mpris:trackid':
                    state.current_song.id,
                    'mpris:length': (
                        'x',
                        (state.current_song.duration or 0)
                        * self.second_microsecond_conversion,
                    ),
                    # TODO this won't work. Need to get the cached version or
                    # give a URL which downloads from the server.
                    'mpris:artUrl':
                    state.current_song.coverArt,
                    'xesam:album':
                    state.current_song.album,
                    'xesam:albumArtist': [state.current_song.artist],
                    'xesam:artist': [state.current_song.artist],
                    'xesam:title':
                    state.current_song.title,
                } if state.current_song else {},
                'Volume':
                0.0 if state.is_muted else state.volume,
                'Position': (
                    'x',
                    int(
                        (state.song_progress or 0)
                        * self.second_microsecond_conversion),
                ),
                'MinimumRate':
                1.0,
                'MaximumRate':
                1.0,
                'CanGoNext':
                has_current_song and has_next_song,
                'CanGoPrevious':
                has_current_song,
                'CanPlay':
                True,
                'CanPause':
                True,
                'CanSeek':
                True,
                'CanControl':
                True,
            },
            'org.mpris.MediaPlayer2.TrackList': {
                'Tracks': state.play_queue,
                'CanEditTracks': True,
            },
        }

    diff_parse_re = re.compile(r"root\['(.*?)'\]\['(.*?)'\](?:\[.*\])?")

    def property_diff(self):
        new_property_dict = self.property_dict()
        diff = DeepDiff(self.current_state, new_property_dict)

        changes = defaultdict(dict)

        for path, change in diff.get('values_changed', {}).items():
            interface, property_name = self.diff_parse_re.match(path).groups()
            changes[interface][property_name] = change['new_value']

        for interface, changed_props in changes.items():
            # If the metadata has changed, just make the entire Metadata object
            # part of the update.
            if 'Metadata' in changed_props.keys():
                changed_props['Metadata'] = new_property_dict[interface][
                    'Metadata']

            if 'Position' in changed_props.keys():
                del changed_props['Position']

            self.connection.emit_signal(
                None,
                '/org/mpris/MediaPlayer2',
                'org.freedesktop.DBus.Properties',
                'PropertiesChanged',
                GLib.Variant(
                    '(sa{sv}as)', (
                        interface,
                        {
                            k: DBusManager.to_variant(v)
                            for k, v in changed_props.items()
                        },
                        [],
                    )),
            )

        self.current_state = new_property_dict
