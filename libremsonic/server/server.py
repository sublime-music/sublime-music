import requests
from typing import List, Optional, Dict

from .api_objects import (SubsonicResponse, License, MusicFolder, Indexes,
                          AlbumInfo, ArtistInfo, VideoInfo, File, Album,
                          Artist, Artists, Directory, Genre)


class Server:
    """Defines a *Sonic server."""

    def __init__(self,
                 name: str = None,
                 hostname: str = None,
                 username: str = None,
                 password: str = None):
        # TODO handle these optionals better.
        self.name: str = name or ''
        self.hostname: str = hostname or ''
        self.username: str = username or ''
        self.password: str = password or ''

    def _get_params(self) -> Dict[str, str]:
        """See Subsonic API Introduction for details."""
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
        """
        Make a post to a *Sonic REST API. Handle all types of errors including
        *Sonic ``<error>`` responses.

        :returns: a SubsonicResponse containing all of the data of the
            response, deserialized
        :raises Exception: needs some work TODO
        """
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
        """
        Used to test connectivity with the server.
        """
        return self._post(self._make_url('ping'))

    def get_license(self) -> License:
        """
        Get details about the software license.
        """
        result = self._post(self._make_url('getLicense'))
        return result.license

    def get_music_folders(self) -> List[MusicFolder]:
        """
        Returns all configured top-level music folders.
        """
        result = self._post(self._make_url('getMusicFolders'))
        return result.musicFolders.musicFolder

    def get_indexes(self,
                    music_folder_id: int = None,
                    if_modified_since: int = None) -> Indexes:
        """
        Returns an indexed structure of all artists.

        :param music_folder_id: If specified, only return artists in the music
            folder with the given ID. See ``getMusicFolders``.
        :param if_modified_since: If specified, only return a result if the
            artist collection has changed since the given time (in milliseconds
            since 1 Jan 1970).
        """
        result = self._post(self._make_url('getIndexes'),
                            musicFolderId=music_folder_id,
                            ifModifiedSince=if_modified_since)
        return result.indexes

    def get_music_directory(self, dir_id) -> Directory:
        """
        Returns a listing of all files in a music directory. Typically used
        to get list of albums for an artist, or list of songs for an album.

        :param dir_id: A string which uniquely identifies the music folder.
            Obtained by calls to ``getIndexes`` or ``getMusicDirectory``.
        """
        result = self._post(self._make_url('getMusicDirectory'),
                            id=str(dir_id))
        return result.directory

    def get_genres(self) -> List[Genre]:
        """
        Returns all genres.
        """
        result = self._post(self._make_url('getGenres'))
        return result.genres.genre

    def get_artists(self, music_folder_id: int = None) -> Artists:
        """
        Similar to getIndexes, but organizes music according to ID3 tags.

        :param music_folder_id: If specified, only return artists in the music
            folder with the given ID. See ``getMusicFolders``.
        """
        result = self._post(self._make_url('getArtists'),
                            musicFolderId=music_folder_id)
        return result.artists

    def get_artist(self, artist_id: int) -> Artist:
        """
        Returns details for an artist, including a list of albums. This method
        organizes music according to ID3 tags.

        :param artist_id: The artist ID.
        """
        result = self._post(self._make_url('getArtist'), id=artist_id)
        return result.artist

    def get_album(self, album_id: int) -> Album:
        """
        Returns details for an album, including a list of songs. This method
        organizes music according to ID3 tags.

        :param album_id: The album ID.
        """
        result = self._post(self._make_url('getAlbum'), id=album_id)
        return result.album

    def get_song(self, song_id: int) -> File:
        """
        Returns details for a song.

        :param song_id: The song ID.
        """
        result = self._post(self._make_url('getSong'), id=song_id)
        return result.song

    def get_videos(self) -> Optional[List[File]]:
        """
        Returns all video files.
        """
        result = self._post(self._make_url('getVideos'))
        return result.videos.video

    def get_video_info(self, video_id: int) -> Optional[VideoInfo]:
        """
        Returns details for a video, including information about available
        audio tracks, subtitles (captions) and conversions.

        :param video_id: The video ID.
        """
        result = self._post(self._make_url('getVideoInfo'), id=video_id)
        return result.videoInfo

    def get_artist_info(self,
                        id: int,
                        count: int = None,
                        include_not_present: bool = None
                        ) -> Optional[ArtistInfo]:
        """
        Returns artist info with biography, image URLs and similar artists,
        using data from last.fm.

        :param id: The artist, album, or song ID.
        :param count: Max number of similar artists to return. Defaults to 20,
            according to API Spec.
        :param include_not_present: Whether to return artists that are not
            present in the media library. Defaults to false according to API
            Spec.
        """
        result = self._post(self._make_url('getArtistInfo'),
                            id=id,
                            count=count,
                            includeNotPresent=include_not_present)
        return result.artistInfo

    def get_artist_info2(self,
                         id: int,
                         count: int = None,
                         include_not_present: bool = None
                         ) -> Optional[ArtistInfo]:
        """
        Similar to getArtistInfo, but organizes music according to ID3 tags.

        :param id: The artist, album, or song ID.
        :param count: Max number of similar artists to return. Defaults to 20,
            according to API Spec.
        :param include_not_present: Whether to return artists that are not
            present in the media library. Defaults to false according to API
            Spec.
        """
        result = self._post(self._make_url('getArtistInfo2'),
                            id=id,
                            count=count,
                            includeNotPresent=include_not_present)
        return result.artistInfo

    def get_album_info(self, id: int) -> Optional[AlbumInfo]:
        """
        Returns album notes, image URLs etc, using data from last.fm.

        :param id: The album or song ID.
        """
        result = self._post(self._make_url('getAlbumInfo'), id=id)
        return result.albumInfo

    def get_album_info2(self, id: int) -> Optional[AlbumInfo]:
        """
        Similar to getAlbumInfo, but organizes music according to ID3 tags.

        :param id: The album or song ID.
        """
        result = self._post(self._make_url('getAlbumInfo2'), id=id)
        return result.albumInfo2

    def get_similar_songs(self, id: int, count: int = None) -> List[File]:
        """
        Returns a random collection of songs from the given artist and similar
        artists, using data from last.fm. Typically used for artist radio
        features.

        :param id: The artist, album or song ID.
        :param count: Max number of songs to return. Defaults to 50 according
            to API Spec.
        """
        result = self._post(self._make_url('getAlbumInfo2'), id=id)
        return result.similarSongs
