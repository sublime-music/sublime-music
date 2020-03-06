import logging
import math
import os
from datetime import datetime
from time import sleep
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode

import requests
from deprecated import deprecated

from .api_objects import (
    AlbumInfo,
    AlbumList,
    AlbumList2,
    AlbumWithSongsID3,
    ArtistInfo,
    ArtistInfo2,
    ArtistsID3,
    ArtistWithAlbumsID3,
    Bookmarks,
    Child,
    Directory,
    Error,
    Genres,
    Indexes,
    InternetRadioStations,
    License,
    Lyrics,
    MusicFolders,
    NowPlaying,
    Playlists,
    PlaylistWithSongs,
    PlayQueue,
    Response,
    ScanStatus,
    SearchResult,
    SearchResult2,
    SearchResult3,
    Shares,
    Songs,
    Starred,
    Starred2,
    User,
    Users,
    VideoInfo,
)


class Server:
    """
    Defines a \\*Sonic server.

    Notes:

    * The ``hls`` endpoint is not supported.
    * The ``getCaptions`` endpoint is not supported
    * None of the podcast endpoints are supported.
    * The ``jukeboxControl`` endpoint is not supported.
    * None of the chat message endpoints are supported.
    * The ``server`` module is stateless. The only thing that it does is allow
      the module's user to query the \\*sonic server via the API.
    """
    class SubsonicServerError(Exception):
        def __init__(self: 'Server.SubsonicServerError', error: Error):
            super().__init__(f'{error.code}: {error.message}')

    def __init__(
        self,
        name: str,
        hostname: str,
        username: str,
        password: str,
        disable_cert_verify: bool,
    ):
        self.name: str = name
        self.hostname: str = hostname
        self.username: str = username
        self.password: str = password
        self.disable_cert_verify: bool = disable_cert_verify

    def _get_params(self) -> Dict[str, str]:
        """See Subsonic API Introduction for details."""
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
    ) -> Response:
        """
        Make a get request to a *Sonic REST API. Handle all types of errors
        including *Sonic ``<error>`` responses.

        :returns: a Response containing all of the data of the
            response, deserialized
        :raises Exception: needs some work TODO
        """
        result = self._get(url, **params)
        subsonic_response = result.json()['subsonic-response']

        # TODO (#122):  make better
        if not subsonic_response:
            raise Exception('Fail!')

        if subsonic_response['status'] == 'failed':
            code, message = (
                subsonic_response['error'].get('code'),
                subsonic_response['error'].get('message'),
            )
            raise Exception(f'Subsonic API Error #{code}: {message}')

        response = Response.from_json(subsonic_response)

        # Check for an error and if it exists, raise it.
        if response.get('error'):
            raise Server.SubsonicServerError(response.error)

        return response

    def do_download(self, url: str, **params) -> bytes:
        download = self._get(url, **params)
        if 'json' in download.headers.get('Content-Type'):
            # TODO (#122): make better
            raise Exception("Didn't expect JSON.")
        return download.content

    def ping(self) -> Response:
        """
        Used to test connectivity with the server.
        """
        return self._get_json(self._make_url('ping'))

    def get_license(self) -> License:
        """
        Get details about the software license.
        """
        result = self._get_json(self._make_url('getLicense'))
        return result.license

    def get_music_folders(self) -> MusicFolders:
        """
        Returns all configured top-level music folders.
        """
        result = self._get_json(self._make_url('getMusicFolders'))
        return result.musicFolders

    def get_indexes(
            self,
            music_folder_id: int = None,
            if_modified_since: int = None,
    ) -> Indexes:
        """
        Returns an indexed structure of all artists.

        :param music_folder_id: If specified, only return artists in the music
            folder with the given ID. See ``getMusicFolders``.
        :param if_modified_since: If specified, only return a result if the
            artist collection has changed since the given time.
        """
        result = self._get_json(
            self._make_url('getIndexes'),
            musicFolderId=music_folder_id,
            ifModifiedSince=if_modified_since)
        return result.indexes

    def get_music_directory(self, dir_id: Union[int, str]) -> Directory:
        """
        Returns a listing of all files in a music directory. Typically used
        to get list of albums for an artist, or list of songs for an album.

        :param dir_id: A string which uniquely identifies the music folder.
            Obtained by calls to ``getIndexes`` or ``getMusicDirectory``.
        """
        result = self._get_json(
            self._make_url('getMusicDirectory'), id=str(dir_id))
        return result.directory

    def get_genres(self) -> Genres:
        """
        Returns all genres.
        """
        result = self._get_json(self._make_url('getGenres'))
        return result.genres

    def get_artists(self, music_folder_id: int = None) -> ArtistsID3:
        """
        Similar to getIndexes, but organizes music according to ID3 tags.

        :param music_folder_id: If specified, only return artists in the music
            folder with the given ID. See ``getMusicFolders``.
        """
        result = self._get_json(
            self._make_url('getArtists'), musicFolderId=music_folder_id)
        return result.artists

    def get_artist(self, artist_id: int) -> ArtistWithAlbumsID3:
        """
        Returns details for an artist, including a list of albums. This method
        organizes music according to ID3 tags.

        :param artist_id: The artist ID.
        """
        result = self._get_json(self._make_url('getArtist'), id=artist_id)
        return result.artist

    def get_album(self, album_id: int) -> AlbumWithSongsID3:
        """
        Returns details for an album, including a list of songs. This method
        organizes music according to ID3 tags.

        :param album_id: The album ID.
        """
        result = self._get_json(self._make_url('getAlbum'), id=album_id)
        return result.album

    def get_song(self, song_id: int) -> Child:
        """
        Returns details for a song.

        :param song_id: The song ID.
        """
        result = self._get_json(self._make_url('getSong'), id=song_id)
        return result.song

    def get_videos(self) -> Optional[List[Child]]:
        """
        Returns all video files.
        """
        result = self._get_json(self._make_url('getVideos'))
        return result.videos.video

    def get_video_info(self, video_id: int) -> Optional[VideoInfo]:
        """
        Returns details for a video, including information about available
        audio tracks, subtitles (captions) and conversions.

        :param video_id: The video ID.
        """
        result = self._get_json(self._make_url('getVideoInfo'), id=video_id)
        return result.videoInfo

    def get_artist_info(
            self,
            id: int,
            count: int = None,
            include_not_present: bool = None,
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
        result = self._get_json(
            self._make_url('getArtistInfo'),
            id=id,
            count=count,
            includeNotPresent=include_not_present,
        )
        return result.artistInfo

    def get_artist_info2(
            self,
            id: int,
            count: int = None,
            include_not_present: bool = None,
    ) -> Optional[ArtistInfo2]:
        """
        Similar to getArtistInfo, but organizes music according to ID3 tags.

        :param id: The artist, album, or song ID.
        :param count: Max number of similar artists to return. Defaults to 20,
            according to API Spec.
        :param include_not_present: Whether to return artists that are not
            present in the media library. Defaults to false according to API
            Spec.
        """
        result = self._get_json(
            self._make_url('getArtistInfo2'),
            id=id,
            count=count,
            includeNotPresent=include_not_present,
        )
        return result.artistInfo2

    def get_album_info(self, id: int) -> Optional[AlbumInfo]:
        """
        Returns album notes, image URLs etc, using data from last.fm.

        :param id: The album or song ID.
        """
        result = self._get_json(self._make_url('getAlbumInfo'), id=id)
        return result.albumInfo

    def get_album_info2(self, id: int) -> Optional[AlbumInfo]:
        """
        Similar to getAlbumInfo, but organizes music according to ID3 tags.

        :param id: The album or song ID.
        """
        result = self._get_json(self._make_url('getAlbumInfo2'), id=id)
        return result.albumInfo

    def get_similar_songs(self, id: int, count: int = None) -> List[Child]:
        """
        Returns a random collection of songs from the given artist and similar
        artists, using data from last.fm. Typically used for artist radio
        features.

        :param id: The artist, album or song ID.
        :param count: Max number of songs to return. Defaults to 50 according
            to API Spec.
        """
        result = self._get_json(
            self._make_url('getSimilarSongs'),
            id=id,
            count=count,
        )
        return result.similarSongs.song

    def get_similar_songs2(self, id: int, count: int = None) -> List[Child]:
        """
        Similar to getSimilarSongs, but organizes music according to ID3 tags.

        :param id: The artist, album or song ID.
        :param count: Max number of songs to return. Defaults to 50 according
            to API Spec.
        """
        result = self._get_json(
            self._make_url('getSimilarSongs2'),
            id=id,
            count=count,
        )
        return result.similarSongs2.song

    def get_top_songs(self, artist: str, count: int = None) -> List[Child]:
        """
        Returns top songs for the given artist, using data from last.fm.

        :param id: The artist name.
        :param count: Max number of songs to return. Defaults to 50 according
            to API Spec.
        """
        result = self._get_json(
            self._make_url('getTopSongs'),
            artist=artist,
            count=count,
        )
        return result.topSongs.song

    def get_album_list(
            self,
            type: str,
            size: int = None,
            offset: int = None,
            from_year: int = None,
            to_year: int = None,
            genre: str = None,
            music_folder_id: int = None,
    ) -> AlbumList:
        """
        Returns a list of random, newest, highest rated etc. albums. Similar to
        the album lists on the home page of the Subsonic web interface.

        :param type: The list type. Must be one of the following: ``random``,
            ``newest``, ``highest``, ``frequent``, ``recent``. Since 1.8.0 you
            can also use ``alphabeticalByName`` or ``alphabeticalByArtist`` to
            page through all albums alphabetically, and ``starred`` to retrieve
            starred albums.  Since 1.10.1 you can use ``byYear`` and
            ``byGenre`` to list albums in a given year range or genre.
        :param size: The number of albums to return. Max 500. Deafult is 10
            according to API Spec.
        :param offset: The list offset. Useful if you for example want to page
            through the list of newest albums. Default is 0 according to API
            Spec.
        :param from_year: Required if ``type`` is ``byYear``. The first year in
            the range. If ``fromYear > toYear`` a reverse chronological list is
            returned.
        :param to_year: Required if ``type`` is ``byYear``. The last year in
            the range.
        :param genre: Required if ``type`` is ``byGenre``. The name of the
            genre, e.g., "Rock".
        :param music_folder_id: (Since 1.11.0) Only return albums in the music
            folder with the given ID. See ``getMusicFolders``.
        """
        result = self._get_json(
            self._make_url('getAlbumList'),
            type=type,
            size=size,
            offset=offset,
            fromYear=from_year,
            toYear=to_year,
            genre=genre,
            musicFolderId=music_folder_id,
        )
        return result.albumList

    def get_album_list2(
            self,
            type: str,
            size: int = None,
            offset: int = None,
            from_year: int = None,
            to_year: int = None,
            genre: str = None,
            music_folder_id: int = None,
    ) -> AlbumList2:
        """
        Similar to getAlbumList, but organizes music according to ID3 tags.

        :param type: The list type. Must be one of the following: ``random``,
            ``newest``, ``frequent``, ``recent``, ``starred``,
            ``alphabeticalByName`` or ``alphabeticalByArtist``. Since 1.10.1
            you can use ``byYear`` and ``byGenre`` to list albums in a given
            year range or genre.
        :param size: The number of albums to return. Max 500. Deafult is 10
            according to API Spec.
        :param offset: The list offset. Useful if you for example want to page
            through the list of newest albums. Default is 0 according to API
            Spec.
        :param from_year: Required if ``type`` is ``byYear``. The first year in
            the range. If ``fromYear > toYear`` a reverse chronological list is
            returned.
        :param to_year: Required if ``type`` is ``byYear``. The last year in
            the range.
        :param genre: Required if ``type`` is ``byGenre``. The name of the
            genre, e.g., "Rock".
        :param music_folder_id: (Since 1.11.0) Only return albums in the music
            folder with the given ID. See ``getMusicFolders``.
        """
        result = self._get_json(
            self._make_url('getAlbumList2'),
            type=type,
            size=size,
            offset=offset,
            fromYear=from_year,
            toYear=to_year,
            genre=genre,
            musicFolderId=music_folder_id,
        )
        return result.albumList2

    def get_random_songs(
            self,
            size: int = None,
            genre: str = None,
            from_year: str = None,
            to_year: str = None,
            music_folder_id: int = None,
    ) -> Songs:
        """
        Returns random songs matching the given criteria.

        :param size: The maximum number of songs to return. Max 500. Defaults
            to 10 according to API Spec.
        :param genre: Only returns songs belonging to this genre.
        :param from_year: Only return songs published after or in this year.
        :param to_year: Only return songs published before or in this year.
        :param music_folder_id: Only return albums in the music folder with the
            given ID. See ``getMusicFolders``.
        """
        result = self._get_json(
            self._make_url('getRandomSongs'),
            size=size,
            genre=genre,
            fromYear=from_year,
            toYear=to_year,
            musicFolderId=music_folder_id,
        )
        return result.randomSongs

    def get_songs_by_genre(
            self,
            genre: str,
            count: int = None,
            offset: int = None,
            music_folder_id: int = None,
    ) -> Songs:
        """
        Returns songs in a given genre.

        :param genre: Only returns songs belonging to this genre.
        :param count: The maximum number of songs to return. Max 500. Defaults
            to 10 according to API Spec.
        :param offset: The offset. Useful if you want to page through the songs
            in a genre.
        :param music_folder_id: (Since 1.12.0) Only return albums in the music
            folder with the given ID. See ``getMusicFolders``.
        """
        result = self._get_json(
            self._make_url('getSongsByGenre'),
            genre=genre,
            count=count,
            offset=offset,
            musicFolderId=music_folder_id,
        )
        return result.songsByGenre

    def get_now_playing(self) -> NowPlaying:
        """
        Returns what is currently being played by all users. Takes no extra
        parameters.
        """
        result = self._get_json(self._make_url('getNowPlaying'))
        return result.nowPlaying

    def get_starred(self, music_folder_id: int = None) -> Starred:
        """
        Returns starred songs, albums and artists.

        :param music_folder_id: (Since 1.12.0) Only return results from the
            music folder with the given ID. See ``getMusicFolders``.
        """
        result = self._get_json(self._make_url('getStarred'))
        return result.starred

    def get_starred2(self, music_folder_id: int = None) -> Starred2:
        """
        Similar to getStarred, but organizes music according to ID3 tags.

        :param music_folder_id: (Since 1.12.0) Only return results from the
            music folder with the given ID. See ``getMusicFolders``.
        """
        result = self._get_json(self._make_url('getStarred2'))
        return result.starred2

    @deprecated(version='1.4.0', reason='You should use search2 instead.')
    def search(
            self,
            artist: str = None,
            album: str = None,
            title: str = None,
            any: str = None,
            count: int = None,
            offset: int = None,
            newer_than: datetime = None,
    ) -> SearchResult:
        """
        Returns a listing of files matching the given search criteria. Supports
        paging through the result.

        :param artist: Artist to search for.
        :param album: Album to searh for.
        :param title: Song title to search for.
        :param any: Searches all fields.
        :param count: Maximum number of results to return.
        :param offset: Search result offset. Used for paging.
        :param newer_than: Only return matches that are newer than this.
        """
        result = self._get_json(
            self._make_url('search'),
            artist=artist,
            album=album,
            title=title,
            any=any,
            count=count,
            offset=offset,
            newerThan=math.floor(newer_than.timestamp()
                                 * 1000) if newer_than else None,
        )
        return result.searchResult

    def search2(
            self,
            query: str,
            artist_count: int = None,
            artist_offset: int = None,
            album_count: int = None,
            album_offset: int = None,
            song_count: int = None,
            song_offset: int = None,
            music_folder_id: int = None,
    ) -> SearchResult2:
        """
        Returns albums, artists and songs matching the given search criteria.
        Supports paging through the result.

        :param query: Search query.
        :param artist_count: Maximum number of artists to return. Defaults to
            20 according to API Spec.
        :param artist_offset: Search result offset for artists. Used for
            paging. Defualts to 0 according to API Spec.
        :param album_count: Maximum number of albums to return. Defaults to 20
            according to API Spec.
        :param album_offset: Search result offset for albums. Used for paging.
            Defualts to 0 according to API Spec.
        :param song_count: Maximum number of songs to return. Defaults to 20
            according to API Spec.
        :param song_offset: Search result offset for songs. Used for paging.
            Defualts to 0 according to API Spec.
        :param music_folder_id: (Since 1.12.0) Only return results from the
            music folder with the given ID. See ``getMusicFolders``.
        """
        result = self._get_json(
            self._make_url('search2'),
            query=query,
            artistCount=artist_count,
            artistOffset=artist_offset,
            albumCount=album_count,
            albumOffset=album_offset,
            songCount=song_count,
            songOffset=song_offset,
            musicFolderId=music_folder_id,
        )
        return result.searchResult2

    def search3(
            self,
            query: str,
            artist_count: int = None,
            artist_offset: int = None,
            album_count: int = None,
            album_offset: int = None,
            song_count: int = None,
            song_offset: int = None,
            music_folder_id: int = None,
    ) -> SearchResult3:
        """
        Similar to search2, but organizes music according to ID3 tags.

        :param query: Search query.
        :param artist_count: Maximum number of artists to return. Defaults to
            20 according to API Spec.
        :param artist_offset: Search result offset for artists. Used for
            paging. Defualts to 0 according to API Spec.
        :param album_count: Maximum number of albums to return. Defaults to 20
            according to API Spec.
        :param album_offset: Search result offset for albums. Used for paging.
            Defualts to 0 according to API Spec.
        :param song_count: Maximum number of songs to return. Defaults to 20
            according to API Spec.
        :param song_offset: Search result offset for songs. Used for paging.
            Defualts to 0 according to API Spec.
        :param music_folder_id: (Since 1.12.0) Only return results from the
            music folder with the given ID. See ``getMusicFolders``.
        """
        result = self._get_json(
            self._make_url('search3'),
            query=query,
            artistCount=artist_count,
            artistOffset=artist_offset,
            albumCount=album_count,
            albumOffset=album_offset,
            songCount=song_count,
            songOffset=song_offset,
            musicFolderId=music_folder_id,
        )
        return result.searchResult3

    def get_playlists(self, username: str = None) -> Playlists:
        """
        Returns all playlists a user is allowed to play.

        :param username: (Since 1.8.0) If specified, return playlists for this
            user rather than for the authenticated user. The authenticated user
            must have admin role if this parameter is used.
        """
        result = self._get_json(
            self._make_url('getPlaylists'), username=username)
        return result.playlists

    def get_playlist(self, id: int = None) -> PlaylistWithSongs:
        """
        Returns a listing of files in a saved playlist.

        :param username: ID of the playlist to return, as obtained by
            ``getPlaylists``.
        """
        result = self._get_json(self._make_url('getPlaylist'), id=id)
        return result.playlist

    def create_playlist(
        self,
        playlist_id: int = None,
        name: str = None,
        song_id: Union[int, List[int]] = None,
    ) -> Union[PlaylistWithSongs, Response]:
        """
        Creates (or updates) a playlist.

        :param playlist_id: The playlist ID. Required if updating.
        :param name: The human-readable name of the playlist. Required if
            creating.
        :param song_id: ID(s) of a song in the playlist. Can be a single ID or
            a list of IDs.
        """
        result = self._get_json(
            self._make_url('createPlaylist'),
            playlistId=playlist_id,
            name=name,
            songId=song_id,
        )

        if result.playlist:
            return result.playlist
        else:
            return result

    def update_playlist(
            self,
            playlist_id: int,
            name: str = None,
            comment: str = None,
            public: bool = None,
            song_id_to_add: Union[int, List[int]] = None,
            song_index_to_remove: Union[int, List[int]] = None,
    ) -> Response:
        """
        Updates a playlist. Only the owner of a playlist is allowed to update
        it.

        :param playlist_id: The playlist ID. Required if updating.
        :param name: The human-readable name of the playlist.
        :param comment: The playlist comment.
        :param public: ``true`` if the playlist should be visible to all users,
            ``false`` otherwise.
        :param song_id_to_add: Add this song with this/these ID(s) to the
            playlist. Can be a single ID or a list of IDs.
        :param song_id_to_remove: Remove the song at this/these position(s) in
            the playlist. Can be a single ID or a list of IDs.
        """
        return self._get_json(
            self._make_url('updatePlaylist'),
            playlistId=playlist_id,
            name=name,
            comment=comment,
            public=public,
            songIdToAdd=song_id_to_add,
            songIndexToRemove=song_index_to_remove,
        )

    def delete_playlist(self, id: int) -> Response:
        """
        Deletes a saved playlist
        """
        return self._get_json(self._make_url('deletePlaylist'), id=id)

    def get_stream_url(
            self,
            id: str,
            max_bit_rate: int = None,
            format: str = None,
            time_offset: int = None,
            size: int = None,
            estimate_content_length: bool = False,
            converted: bool = False,
    ) -> str:
        """
        Gets the URL to stream a given file.

        :param id: A string which uniquely identifies the file to stream.
            Obtained by calls to ``getMusicDirectory``.
        :param maxBitRate: (Since 1.2.0) If specified, the server will attempt
            to limit the bitrate to this value, in kilobits per second. If set
            to zero, no limit is imposed.
        :param format: (Since 1.6.0) Specifies the preferred target format
            (e.g., "mp3" or "flv") in case there are multiple applicable
            transcodings. Starting with 1.9.0 you can use the special value
            "raw" to disable transcoding.
        :param timeOffset: Only applicable to video streaming. If specified,
            start streaming at the given offset (in seconds) into the video.
            Typically used to implement video skipping.
        :param size: (Since 1.6.0) Only applicable to video streaming.
            Requested video size specified as WxH, for instance "640x480".
        :param estimateContentLength: (Since 1.8.0). If set to ``True``, the
            *Content-Length* HTTP header will be set to an estimated value for
            transcoded or downsampled media. Defaults to False according to the
            API Spec.
        :param converted: (Since 1.14.0) Only applicable to video streaming.
            Subsonic can optimize videos for streaming by converting them to
            MP4. If a conversion exists for the video in question, then setting
            this parameter to ``True`` will cause the converted video to be
            returned instead of the original. Defaults to False according to
            the API Spec.
        """
        params = dict(
            **self._get_params(),
            id=id,
            maxBitRate=max_bit_rate,
            format=format,
            timeOffset=time_offset,
            size=size,
            estimateContentLength=estimate_content_length,
            converted=converted,
        )
        params = {k: v for k, v in params.items() if v}
        return self._make_url('stream') + '?' + urlencode(params)

    def download(self, id: str) -> bytes:
        """
        Downloads a given media file. Similar to stream, but this method
        returns the original media data without transcoding or downsampling.

        :param id: A string which uniquely identifies the file to stream.
            Obtained by calls to ``getMusicDirectory``.
        """
        return self.do_download(self._make_url('download'), id=id)

    def get_cover_art(self, id: str, size: int = 1000) -> bytes:
        """
        Returns the cover art image in binary form.

        :param id: The ID of a song, album or artist.
        :param size: If specified, scale image to this size.
        """
        return self.do_download(
            self._make_url('getCoverArt'), id=id, size=size)

    def get_cover_art_url(self, id: str, size: int = 1000) -> str:
        """
        Returns the URL of the cover art image.

        :param id: The ID of a song, album or artist.
        :param size: If specified, scale image to this size.
        """
        params = dict(**self._get_params(), id=id, size=size)
        params = {k: v for k, v in params.items() if v}
        return self._make_url('getCoverArt') + '?' + urlencode(params)

    def get_lyrics(self, artist: str = None, title: str = None) -> Lyrics:
        """
        Searches for and returns lyrics for a given song.

        :param artist: The artist name.
        :param title: The song title.
        """
        result = self._get_json(
            self._make_url('getLyrics'),
            artist=artist,
            title=title,
        )
        return result.lyrics

    def get_avatar(self, username: str) -> bytes:
        """
        Returns the avatar (personal image) for a user.

        :param username: the user in question.
        """
        return self.do_download(self._make_url('getAvatar'), username=username)

    def star(
            self,
            id: Union[int, List[int]] = None,
            album_id: Union[int, List[int]] = None,
            artist_id: Union[int, List[int]] = None,
    ) -> Response:
        """
        Attaches a star to a song, album or artist.

        :param id: The ID(s) of the file(s) (song(s)) or folder(s)
            (album(s)/artist(s)) to star. Can be a single ID or a list of IDs.
        :param album_id: The ID(s) of an album/albums to star. Use this rather
            than ``id`` if the client accesses the media collection according
            to ID3 tags rather than file structure. Can be a single ID or a
            list of IDs.
        :param artist_id: The ID(s) of an artist/artists to star. Use this
            rather than ``id`` if the client accesses the media collection
            according to ID3 tags rather than file structure. Can be a single
            ID or a list of IDs.
        """
        return self._get_json(
            self._make_url('star'),
            id=id,
            albumId=album_id,
            artistId=artist_id,
        )

    def unstar(
            self,
            id: Union[int, List[int]] = None,
            album_id: Union[int, List[int]] = None,
            artist_id: Union[int, List[int]] = None,
    ) -> Response:
        """
        Removes the star from a song, album or artist.

        :param id: The ID(s) of the file(s) (song(s)) or folder(s)
            (album(s)/artist(s)) to star. Can be a single ID or a list of IDs.
        :param album_id: The ID(s) of an album/albums to star. Use this rather
            than ``id`` if the client accesses the media collection according
            to ID3 tags rather than file structure. Can be a single ID or a
            list of IDs.
        :param artist_id: The ID(s) of an artist/artists to star. Use this
            rather than ``id`` if the client accesses the media collection
            according to ID3 tags rather than file structure. Can be a single
            ID or a list of IDs.
        """
        return self._get_json(
            self._make_url('unstar'),
            id=id,
            albumId=album_id,
            artistId=artist_id,
        )

    def set_rating(self, id: int, rating: int) -> Response:
        """
        Sets the rating for a music file.

        :param id: A string which uniquely identifies the file (song) or folder
            (album/artist) to rate.
        :param rating: The rating between 1 and 5 (inclusive), or 0 to remove
            the rating.
        """
        return self._get_json(
            self._make_url('setRating'), id=id, rating=rating)

    def scrobble(
            self,
            id: int,
            time: datetime = None,
            submission: bool = True,
    ) -> Response:
        """
        Registers the local playback of one or more media files. Typically used
        when playing media that is cached on the client. This operation
        includes the following:

            * "Scrobbles" the media files on last.fm if the user has configured
              his/her last.fm credentials on the Subsonic server (Settings >
              Personal).
            * Updates the play count and last played timestamp for the media
              files. (Since 1.11.0)
            * Makes the media files appear in the "Now playing" page in the web
              app, and appear in the list of songs returned by
              ``getNowPlaying`` (Since 1.11.0)

        Since 1.8.0 you may specify multiple id (and optionally time)
        parameters to scrobble multiple files.

        :param id: The ID of the file to scrobble.
        :param time: (Since 1.8.0) The time at which the song was listened to.
        :param submission: Whether this is a "submission" or a "now playing"
            notification.
        """
        return self._get_json(
            self._make_url('scrobble'),
            id=id,
            time=time,
            submission=submission,
        )

    def get_shares(self) -> Shares:
        """
        Returns information about shared media this user is allowed to manage.
        Takes no extra parameters.
        """
        result = self._get_json(self._make_url('getShares'))
        return result.shares

    def create_share(
            self,
            id: Union[int, List[int]],
            description: str = None,
            expires: datetime = None,
    ) -> Shares:
        """
        Creates a public URL that can be used by anyone to stream music or
        video from the Subsonic server. The URL is short and suitable for
        posting on Facebook, Twitter etc. Note: The user must be authorized to
        share (see Settings > Users > User is allowed to share files with
        anyone).

        :param id: ID(s) of (a) song(s), album(s) or video(s) to share. Can be
            a single ID or a list of IDs.
        :param description: A user-defined description that will be displayed
            to people visiting the shared media.
        :param expires: The time at which the share expires.
        """
        result = self._get_json(
            self._make_url('createShare'),
            id=id,
            description=description,
            expires=expires,
        )
        return result.shares

    def update_share(
            self,
            id: int,
            description: str = None,
            expires: datetime = None,
    ) -> Response:
        """
        Updates the description and/or expiration date for an existing share.

        :param id: ID of the share to update.
        :param description: A user-defined description that will be displayed
            to people visiting the shared media.
        :param expires: The time at which the share expires.
        """
        return self._get_json(
            self._make_url('updateShare'),
            id=id,
            description=description,
            expires=expires,
        )

    def delete_share(self, id: int) -> Response:
        """
        Deletes an existing share.

        :param id: ID of the share to delete.
        """
        return self._get_json(self._make_url('deleteShare'), id=id)

    def get_internet_radio_stations(self) -> InternetRadioStations:
        """
        Returns all internet radio stations. Takes no extra parameters.
        """
        result = self._get_json(self._make_url('getInternetRadioStations'))
        return result.internetRadioStations

    def create_internet_radio_station(
            self,
            stream_url: str,
            name: str,
            homepage_url: str = None,
    ) -> Response:
        """
        Adds a new internet radio station. Only users with admin privileges are
        allowed to call this method.

        :param stream_url: The stream URL for the station.
        :param name: The user-defined name for the station.
        :param homepage_url: The home page URL for the station.
        """
        return self._get_json(
            self._make_url('createInternetRadioStation'),
            streamUrl=stream_url,
            name=name,
            homepageUrl=homepage_url,
        )

    def update_internet_radio_station(
            self,
            id: int,
            stream_url: str,
            name: str,
            homepage_url: str = None,
    ) -> Response:
        """
        Updates an existing internet radio station. Only users with admin
        privileges are allowed to call this method.

        :param id: The ID for the station.
        :param stream_url: The stream URL for the station.
        :param name: The user-defined name for the station.
        :param homepage_url: The home page URL for the station.
        """
        return self._get_json(
            self._make_url('updateInternetRadioStation'),
            id=id,
            streamUrl=stream_url,
            name=name,
            homepageUrl=homepage_url,
        )

    def delete_internet_radio_station(self, id: int) -> Response:
        """
        Deletes an existing internet radio station. Only users with admin
        privileges are allowed to call this method.

        :param id: The ID for the station.
        """
        return self._get_json(
            self._make_url('deleteInternetRadioStation'), id=id)

    def get_user(self, username: str) -> User:
        """
        Get details about a given user, including which authorization roles and
        folder access it has. Can be used to enable/disable certain features in
        the client, such as jukebox control.

        :param username: The name of the user to retrieve. You can only
            retrieve your own user unless you have admin privileges.
        """
        result = self._get_json(self._make_url('getUser'), username=username)
        return result.user

    def get_users(self) -> Users:
        """
        Get details about all users, including which authorization roles and
        folder access they have. Only users with admin privileges are allowed
        to call this method.
        """
        result = self._get_json(self._make_url('getUsers'))
        return result.users

    def create_user(
            self,
            username: str,
            password: str,
            email: str,
            ldap_authenticated: bool = False,
            admin_role: bool = False,
            settings_role: bool = True,
            stream_role: bool = True,
            jukebox_role: bool = False,
            download_role: bool = False,
            upload_role: bool = False,
            playlist_role: bool = False,
            covert_art_role: bool = False,
            comment_role: bool = False,
            podcast_role: bool = False,
            share_role: bool = False,
            video_conversion_role: bool = False,
            music_folder_id: Union[int, List[int]] = None,
    ) -> Response:
        """
        Creates a new Subsonic user.

        :param username: The name of the new user.
        :param password: The password of the new user, either in clear text or
            hex-encoded.
        :param email: The email address of the new user.
        :param ldap_authenticated: Whether the user is authenicated in LDAP.
        :param admin_role: Whether the user is administrator.
        :param settings_role: Whether the user is allowed to change personal
            settings and password.
        :param stream_role: Whether the user is allowed to play files.
        :param jukebox_role: Whether the user is allowed to play files in
            jukebox mode.
        :param download_role: Whether the user is allowed to download files.
        :param upload_role: Whether the user is allowed to upload files.
        :param playlist_role: Whether the user is allowed to create and delete
            playlists. Since 1.8.0, changing this role has no effect.
        :param covert_art_role: Whether the user is allowed to change cover art
            and tags.
        :param comment_role: Whether the user is allowed to create and edit
            comments and ratings.
        :param podcast_role: Whether the user is allowed to administrate
            Podcasts.
        :param share_role: (Since 1.8.0) Whether the user is allowed to share
            files with anyone.
        :param video_conversion_role: (Since 1.15.0) Whether the user is
            allowed to start video conversions.
        :param music_folder_id: (Since 1.12.0) IDs of the music folders the
            user is allowed access to. Can be a single ID or a list of IDs.
        """
        return self._get_json(
            self._make_url('createUser'),
            username=username,
            password=password,
            email=email,
            ldapAuthenticated=ldap_authenticated,
            adminRole=admin_role,
            settingsRole=settings_role,
            streamRole=stream_role,
            jukeboxRole=jukebox_role,
            downloadRole=download_role,
            uploadRole=upload_role,
            playlistRole=playlist_role,
            coverArtRole=covert_art_role,
            commentRole=comment_role,
            podcastRole=podcast_role,
            shareRole=share_role,
            videoConversionRole=video_conversion_role,
            musicFolderId=music_folder_id,
        )

    def update_user(
            self,
            username: str,
            password: str = None,
            email: str = None,
            ldap_authenticated: bool = False,
            admin_role: bool = False,
            settings_role: bool = True,
            stream_role: bool = True,
            jukebox_role: bool = False,
            download_role: bool = False,
            upload_role: bool = False,
            playlist_role: bool = False,
            covert_art_role: bool = False,
            comment_role: bool = False,
            podcast_role: bool = False,
            share_role: bool = False,
            video_conversion_role: bool = False,
            music_folder_id: Union[int, List[int]] = None,
    ) -> Response:
        """
        Modifies an existing Subsonic user.

        :param username: The name of the user.
        :param password: The password of the user, either in clear text or
            hex-encoded.
        :param email: The email address of the user.
        :param ldap_authenticated: Whether the user is authenicated in LDAP.
        :param admin_role: Whether the user is administrator.
        :param settings_role: Whether the user is allowed to change personal
            settings and password.
        :param stream_role: Whether the user is allowed to play files.
        :param jukebox_role: Whether the user is allowed to play files in
            jukebox mode.
        :param download_role: Whether the user is allowed to download files.
        :param upload_role: Whether the user is allowed to upload files.
        :param playlist_role: Whether the user is allowed to create and delete
            playlists. Since 1.8.0, changing this role has no effect.
        :param covert_art_role: Whether the user is allowed to change cover art
            and tags.
        :param comment_role: Whether the user is allowed to create and edit
            comments and ratings.
        :param podcast_role: Whether the user is allowed to administrate
            Podcasts.
        :param share_role: (Since 1.8.0) Whether the user is allowed to share
            files with anyone.
        :param video_conversion_role: (Since 1.15.0) Whether the user is
            allowed to start video conversions.
        :param music_folder_id: (Since 1.12.0) IDs of the music folders the
            user is allowed access to. Can be a single ID or a list of IDs.
        """
        return self._get_json(
            self._make_url('updateUser'),
            username=username,
            password=password,
            email=email,
            ldapAuthenticated=ldap_authenticated,
            adminRole=admin_role,
            settingsRole=settings_role,
            streamRole=stream_role,
            jukeboxRole=jukebox_role,
            downloadRole=download_role,
            uploadRole=upload_role,
            playlistRole=playlist_role,
            coverArtRole=covert_art_role,
            commentRole=comment_role,
            podcastRole=podcast_role,
            shareRole=share_role,
            videoConversionRole=video_conversion_role,
            musicFolderId=music_folder_id,
        )

    def delete_user(self, username: str) -> Response:
        """
        Deletes an existing Subsonic user.

        :param username: The name of the new user.
        """
        return self._get_json(self._make_url('deleteUser'), username=username)

    def change_password(self, username: str, password: str) -> Response:
        """
        Changes the password of an existing Subsonic user. You can only change
        your own password unless you have admin privileges.

        :param username: The name of the user which should change its password.
        :param password: The new password of the new user, either in clear text
            of hex-encoded.
        """
        return self._get_json(
            self._make_url('changePassword'),
            username=username,
            password=password,
        )

    def get_bookmarks(self) -> Bookmarks:
        """
        Returns all bookmarks for this user. A bookmark is a position within a
        certain media file.
        """
        result = self._get_json(self._make_url('getBookmarks'))
        return result.bookmarks

    def create_bookmarks(
            self,
            id: int,
            position: int,
            comment: str = None,
    ) -> Response:
        """
        Creates or updates a bookmark (a position within a media file).
        Bookmarks are personal and not visible to other users.

        :param id: ID of the media file to bookmark. If a bookmark already
            exists for this file it will be overwritten.
        :param position: The position (in milliseconds) within the media file.
        :param comment: A user-defined comment.
        """
        return self._get_json(
            self._make_url('createBookmark'),
            id=id,
            position=position,
            comment=comment,
        )

    def delete_bookmark(self, id: int) -> Response:
        """
        Deletes the bookmark for a given file.

        :param id: ID of the media file for which to delete the bookmark. Other
            users' bookmarks are not affected.
        """
        return self._get_json(self._make_url('deleteBookmark'), id=id)

    def get_play_queue(self) -> Optional[PlayQueue]:
        """
        Returns the state of the play queue for this user (as set by
        ``savePlayQueue``). This includes the tracks in the play queue, the
        currently playing track, and the position within this track. Typically
        used to allow a user to move between different clients/apps while
        retaining the same play queue (for instance when listening to an audio
        book).
        """
        result = self._get_json(self._make_url('getPlayQueue'))
        return result.playQueue

    def save_play_queue(
            self,
            id: Union[int, List[int]],
            current: int = None,
            position: int = None,
    ) -> Response:
        """
        Saves the state of the play queue for this user. This includes the
        tracks in the play queue, the currently playing track, and the position
        within this track. Typically used to allow a user to move between
        different clients/apps while retaining the same play queue (for
        instance when listening to an audio book).

        :param id: ID(s) of a/the song(s) in the play queue. Can be either a
            single ID or a list of IDs.
        :param current: The ID of the current playing song.
        :param position: The position in milliseconds within the currently
            playing song.
        """
        return self._get_json(
            self._make_url('savePlayQueue'),
            id=id,
            current=current,
            position=position,
        )

    def get_scan_status(self) -> ScanStatus:
        """
        Returns the current status for media library scanning. Takes no extra
        parameters.
        """
        result = self._get_json(self._make_url('getScanStatus'))
        return result.scanStatus

    def start_scan(self) -> ScanStatus:
        """
        Initiates a rescan of the media libraries. Takes no extra parameters.
        """
        result = self._get_json(self._make_url('startScan'))
        return result.scanStatus
