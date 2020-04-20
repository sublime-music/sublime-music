import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
from typing import Any, Dict, Sequence, Optional, Tuple, Union

import requests

from .api_objects import Response
from .. import Adapter, api_objects as API, ConfigParamDescriptor


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
        self.disable_cert_verify = config.get('disable_cert_verify')

        # TODO support XML | JSON

    # Availability Properties
    # =========================================================================
    @property
    def can_service_requests(self) -> bool:
        try:
            self._get_json('ping', timeout=2)
            return True
        except Exception:
            logging.exception(f'Could not connect to {self.hostname}')
            return False

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

    def _get(
            self,
            url: str,
            timeout: Union[float, Tuple[float, float], None] = None,
            **params,
    ) -> Any:
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

        if self._is_mock:
            return self._get_mock_data()

        result = requests.get(
            url,
            params=params,
            verify=not self.disable_cert_verify,
            timeout=timeout,
        )

        # TODO (#122): make better
        if result.status_code != 200:
            raise Exception(f'[FAIL] get: {url} status={result.status_code}')

        logging.info(f'[FINISH] get: {url}')
        return result

    def _get_json(
        self,
        url: str,
        **params: Union[None, str, datetime, int, Sequence[int]],
    ) -> Response:
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

        logging.debug(f'Response from {url}', subsonic_response)
        return Response.from_dict(subsonic_response)

    # Helper Methods for Testing
    _get_mock_data: Any = None
    _is_mock: bool = False

    def _set_mock_data(self, data: Any):
        class MockResult:
            def __init__(self, content: Any):
                self._content = content

            def content(self) -> Any:
                return self._content

            def json(self) -> Any:
                return json.loads(self._content)

        def get_mock_data() -> Any:
            if type(data) == Exception:
                raise data
            return MockResult(data)

        self._get_mock_data = get_mock_data

    # Data Retrieval Methods
    # =========================================================================
    can_get_playlists = True

    def get_playlists(self) -> Sequence[API.Playlist]:
        response = self._get_json(self._make_url('getPlaylists')).playlists
        if not response:
            return []
        return response.playlist

    can_get_playlist_details = True

    def get_playlist_details(
            self,
            playlist_id: str,
    ) -> API.PlaylistDetails:
        result = self._get_json(
            self._make_url('getPlaylist'),
            id=playlist_id,
        ).playlist
        print(result)
        return result
        # assert result
        # result['duration'] = result.get('duration') or sum(
        #     s.get('duration') or 0 for s in result['entry'])
        # result['songCount'] = result.get('songCount') or len(result['entry'])
        # songs = [Song(id=s['id']) for s in result['entry']]
        # del result['entry']
        # return API.PlaylistDetails(**self._to_snake_case(result), songs=songs)
