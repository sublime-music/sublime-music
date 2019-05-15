import requests

from .api_objects import SubsonicResponse, License


class Server:
    """Defines a *Sonic server."""

    def __init__(self, name=None, hostname=None, username=None, password=None):
        self.name = name
        self.hostname = hostname
        self.username = username
        self.password = password

    def _get_params(self):
        return dict(
            u=self.username,
            p=self.password,
            c='LibremSonic',
            f='json',
            v='1.15.0',
        )

    def _make_url(self, endpoint):
        return f'{self.hostname}/rest/{endpoint}.view'

    def _post(self, url, **params):
        params = {**self._get_params(), **params}
        result = requests.post(url, data=params)
        subsonic_response = result.json()['subsonic-response']
        # TODO make better
        if not subsonic_response:
            raise Exception('Fail!')

        print(subsonic_response)

        response = SubsonicResponse.from_json(subsonic_response)

        # Check for an error and if it exists, raise it.
        if response.get('error'):
            raise response.error.as_exception()

        return response

    def ping(self) -> SubsonicResponse:
        return self._post(self._make_url('ping'))

    def get_license(self) -> License:
        result = self._post(self._make_url('getLicense'))
        return result.license

    def get_music_folders(self):
        result = self._post(self._make_url('getMusicFolders'))
        return result.musicFolders

    def get_indexes(self):
        result = self._post(self._make_url('getIndexes'))
        return result

    def get_music_directory(self, dir_id):
        result = self._post(self._make_url('getIndexes'), id=str(dir_id))
        return result

    def get_genres(self):
        result = self._post(self._make_url('getGenres'))
        return result
