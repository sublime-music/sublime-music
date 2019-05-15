import requests
from typing import List, Optional

from .api_objects import (SubsonicResponse, License, MusicFolder, Indexes,
                          ArtistInfo, VideoInfo, File, Album, Artist, Artists,
                          Directory, Genre)


class Server:
    """Defines a *Sonic server."""

    def __init__(self,
                 name: str = None,
                 hostname: str = None,
                 username: str = None,
                 password: str = None):
        self.name: Optional[str] = name
        self.hostname: Optional[str] = hostname
        self.username: Optional[str] = username
        self.password: Optional[str] = password

    def _get_params(self):
        return dict(
            u=self.username,
            p=self.password,
            c='LibremSonic',
            f='json',
            v='1.15.0',
        )

    def _make_url(self, endpoint: str) -> str:
        return f'{self.hostname}/rest/{endpoint}.view'

    def _post(self, url, **params) -> SubsonicResponse:
        params = {**self._get_params(), **params}
        result = requests.post(url, data=params)
        # TODO make better
        if result.status_code != 200:
            raise Exception(f'Fail! {result.status_code}')

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

    def get_music_folders(self) -> List[MusicFolder]:
        result = self._post(self._make_url('getMusicFolders'))
        return result.musicFolders.musicFolder

    def get_indexes(self,
                    music_folder_id: int = None,
                    if_modified_since: int = None) -> Indexes:
        result = self._post(self._make_url('getIndexes'),
                            musicFolderId=music_folder_id,
                            ifModifiedSince=if_modified_since)
        return result.indexes

    def get_music_directory(self, dir_id) -> Directory:
        result = self._post(self._make_url('getMusicDirectory'),
                            id=str(dir_id))
        return result.directory

    def get_genres(self) -> List[Genre]:
        result = self._post(self._make_url('getGenres'))
        return result.genres.genre

    def get_artists(self, music_folder_id: int = None) -> Artists:
        result = self._post(self._make_url('getArtists'),
                            musicFolderId=music_folder_id)
        return result.artists

    def get_artist(self, artist_id: int) -> Artist:
        result = self._post(self._make_url('getArtist'), id=artist_id)
        return result.artist

    def get_album(self, album_id: int) -> Album:
        result = self._post(self._make_url('getAlbum'), id=album_id)
        return result.album

    def get_song(self, song_id: int) -> File:
        result = self._post(self._make_url('getSong'), id=song_id)
        return result.song

    def get_videos(self) -> Optional[List[File]]:
        result = self._post(self._make_url('getVideos'))
        return result.videos.video

    def get_video_info(self, video_id: int) -> Optional[VideoInfo]:
        result = self._post(self._make_url('getVideoInfo'), id=video_id)
        return result.videoInfo

    def get_artist_info(self,
                        artist_id: int,
                        count: int = None,
                        include_not_present: bool = None
                        ) -> Optional[ArtistInfo]:
        result = self._post(self._make_url('getArtistInfo'),
                            id=artist_id,
                            count=count,
                            includeNotPresent=include_not_present)
        return result.artistInfo
