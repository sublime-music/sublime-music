from datetime import datetime
from typing import Any, Dict, List

from libremsonic.from_json import from_json as _from_json


class APIObject:
    @classmethod
    def from_json(cls, data):
        return _from_json(cls, data)

    def get(self, field, default=None):
        return getattr(self, field, default)

    def __repr__(self):
        annotations: Dict[str, Any] = self.get('__annotations__', {})
        typename = type(self).__name__
        fieldstr = ' '.join([
            f'{field}={getattr(self, field)!r}'
            for field in annotations.keys() if hasattr(self, field)
        ])
        return f'<{typename} {fieldstr}>'


class SubsonicError(APIObject):
    code: int
    message: str

    def as_exception(self):
        return Exception(f'{self.code}: {self.message}')


class License(APIObject):
    valid: bool
    email: str
    licenseExpires: datetime
    trialExpires: datetime


class MusicFolder(APIObject):
    id: int
    name: str


class File(APIObject):
    id: int
    parent: int
    title: str
    isDir: bool
    album: str
    artist: str
    track: str
    year: str
    genre: str
    coverArt: int
    size: int
    contentType: str
    isVideo: bool
    transcodedSuffix: str
    transcodedContentType: str
    suffix: str
    duration: int
    bitRate: int
    path: str
    playCount: int
    created: datetime


class Album(APIObject):
    id: int
    name: str
    artist: str
    artistId: int
    coverArt: str
    songCount: int
    duration: int
    created: datetime
    year: str
    genre: str

    song: List[File]


class Artist(APIObject):
    id: int
    name: str
    coverArt: str
    albumCount: int
    album: List[Album]


class Shortcut(APIObject):
    id: int
    name: str


class Index(APIObject):
    name: str
    artist: List[Artist]


class Indexes(APIObject):
    lastModified: int
    ignoredArticles: str
    index: List[Index]
    shortcut: List[Shortcut]
    child: List[File]


class Directory(APIObject):
    id: int
    parent: str
    name: str
    playCount: int
    child: List[File]


class Genre(APIObject):
    songCount: int
    albumCount: int
    vvalue: str


class MusicFolders(APIObject):
    musicFolder: List[MusicFolder]


class Genres(APIObject):
    genre: List[Genre]


class Artists(APIObject):
    index: List[Index]


class Videos(APIObject):
    video: List[File]


class VideoInfo(APIObject):
    # TODO implement when I have videos
    pass


class ArtistInfo(APIObject):
    biography: str
    musicBrainzId: str
    lastFmUrl: str
    smallImageUrl: str
    mediumImageUrl: str
    largeImageUrl: str
    similarArtist: List[Artist]


class AlbumInfo(APIObject):
    notes: str
    musicBrainzId: str
    lastFmUrl: str
    smallImageUrl: str
    mediumImageUrl: str
    largeImageUrl: str


class SimilarSongs(APIObject):
    song: List[File]


class SubsonicResponse(APIObject):
    status: str
    version: str
    license: License
    error: SubsonicError
    musicFolders: MusicFolders
    indexes: Indexes
    directory: Directory
    genres: Genres
    artists: Artists
    artist: Artist
    album: Album
    song: File
    videos: Videos
    videoInfo: VideoInfo
    artistInfo: ArtistInfo
    artistInfo2: ArtistInfo
    albumInfo: AlbumInfo
    albumInfo2: AlbumInfo
    similarSongs: SimilarSongs
