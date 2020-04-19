import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
from typing import Any, Dict, List, Optional, Union

import requests

from sublime.adapters.api_objects import (
    Playlist,
    PlaylistDetails,
    Song,
)
from .. import Adapter, ConfigParamDescriptor


class SubsonicAdapter(Adapter):
    """
    Defines an adapter which retrieves its data from a Subsonic server
    """
    # Configuration and Initialization Properties
    # =========================================================================
    @staticmethod
    def get_config_parameters() -> Dict[str, ConfigParamDescriptor]:
        return {
            'server_address':
            ConfigParamDescriptor(str, 'Server address'),
            'username':
            ConfigParamDescriptor(str, 'Username'),
            'password':
            ConfigParamDescriptor('password', 'Password'),
            'disable_cert_verify':
            ConfigParamDescriptor('password', 'Password', False),
        }

    @staticmethod
    def verify_configuration(
            config: Dict[str, Any]) -> Dict[str, Optional[str]]:
        errors: Dict[str, Optional[str]] = {}

        # TODO: verify the URL
        return errors

    def __init__(self, config: dict, data_directory: Path):
        self.hostname = config['server_address']
        self.username = config['username']
        self.password = config['password']
        self.disable_cert_verify = config['disable_cert_verify']

    # Availability Properties
    # =========================================================================
    @property
    def can_service_requests(self) -> bool:
        # TODO: detect ping
        return True

    # Helper mothods for making requests
    # =========================================================================
    def _get_params(self) -> Dict[str, str]:
        """
        Gets the parameters that are needed for all requests to the Subsonic
        API. See Subsonic API Introduction for details.
        """
        return {
            'u': self.username,
            'p': self.password,
            'c': 'Sublime Music',
            'f': 'json',
            'v': '1.15.0',
        }

    def _make_url(self, endpoint: str) -> str:
        return f'{self.hostname}/rest/{endpoint}.view'

    # def _get(self, url, timeout=(3.05, 2), **params):
    def _get(self, url: str, **params) -> Any:
        params = {**self._get_params(), **params}
        logging.info(f'[START] get: {url}')

        if os.environ.get('SUBLIME_MUSIC_DEBUG_DELAY'):
            logging.info(
                "SUBLIME_MUSIC_DEBUG_DELAY enabled. Pausing for "
                f"{os.environ['SUBLIME_MUSIC_DEBUG_DELAY']} seconds.")
            sleep(float(os.environ['SUBLIME_MUSIC_DEBUG_DELAY']))

        # Deal with datetime parameters (convert to milliseconds since 1970)
        for k, v in params.items():
            if type(v) == datetime:
                params[k] = int(v.timestamp() * 1000)

        result = requests.get(
            url,
            params=params,
            verify=not self.disable_cert_verify,
            # timeout=timeout,
        )
        # TODO (#122): make better
        if result.status_code != 200:
            raise Exception(f'[FAIL] get: {url} status={result.status_code}')

        logging.info(f'[FINISH] get: {url}')
        return result

    def _get_json(
        self,
        url: str,
        **params: Union[None, str, datetime, int, List[int]],
    ) -> Dict[str, Any]:
        """
        Make a get request to a *Sonic REST API. Handle all types of errors
        including *Sonic ``<error>`` responses.

        :returns: a dictionary of the subsonic response.
        :raises Exception: needs some work TODO
        """
        result = self._get(url, **params)
        subsonic_response = result.json().get('subsonic-response')

        # TODO (#122):  make better
        if not subsonic_response:
            raise Exception(f'[FAIL] get: invalid JSON from {url}')

        if subsonic_response['status'] == 'failed':
            code, message = (
                subsonic_response['error'].get('code'),
                subsonic_response['error'].get('message'),
            )
            raise Exception(f'Subsonic API Error #{code}: {message}')

        return subsonic_response

    _snake_case_re = re.compile(r'(?<!^)(?=[A-Z])')

    def _to_snake_case(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        return {
            self._snake_case_re.sub('_', k).lower(): v
            for k, v in obj.items()
        }

    # Data Retrieval Methods
    # =========================================================================
    can_get_playlists = True

    def get_playlists(self) -> List[Playlist]:
        result = [
            {
                **p,
                'duration':
                timedelta(
                    seconds=p['duration']) if p.get('duration') else None,
            } for p in self._get_json(self._make_url('getPlaylists')).get(
                'playlists', {}).get('playlist')
        ]
        return [Playlist(**self._to_snake_case(p)) for p in result]

    can_get_playlist_details = True

    def get_playlist_details(
            self,
            playlist_id: str,
    ) -> PlaylistDetails:
        result = self._get_json(
            self._make_url('getPlaylist'),
            id=playlist_id,
        ).get('playlist')
        print(result)
        assert result
        result['duration'] = result.get('duration') or sum(
            s.get('duration') or 0 for s in result['entry'])
        result['songCount'] = result.get('songCount') or len(result['entry'])
        songs = [Song(id=s['id']) for s in result['entry']]
        del result['entry']
        return PlaylistDetails(**self._to_snake_case(result), songs=songs)
