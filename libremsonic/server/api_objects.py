import typing
from typing import Dict, List, Any, Type
from datetime import datetime
from dateutil import parser


def _from_json(cls, data):
    """
    Converts data from a JSON parse into Python data structures.

    Arguments:

    cls: the template class to deserialize into
    data: the data to deserialize to the class
    """
    # Approach for deserialization here:
    # https://stackoverflow.com/a/40639688/2319844

    # If it's a forward reference, evaluate it to figure out the actual
    # type. This allows for types that have to be put into a string.
    if isinstance(cls, typing.ForwardRef):
        cls = cls._evaluate(globals(), locals())

    annotations: Dict[str, Type] = getattr(cls, '__annotations__', {})

    # Handle primitive of objects
    if data is None:
        instance = None
    elif cls == str:
        instance = data
    elif cls == int:
        instance = int(data)
    elif cls == bool:
        instance = bool(data)
    elif cls == datetime:
        instance = parser.parse(data)

    # Handle generics. List[*], Dict[*, *] in particular.
    elif type(cls) == typing._GenericAlias:
        # Having to use this because things changed in Python 3.7.
        class_name = cls._name

        # TODO: this is not very elegant since it doesn't allow things which
        # sublass from List or Dict.
        if class_name == 'List':
            list_type = cls.__args__[0]
            instance: List[list_type] = list()
            for value in data:
                instance.append(_from_json(list_type, value))

        elif class_name == 'Dict':
            key_type, val_type = cls.__args__
            instance: Dict[key_type, val_type] = dict()
            for key, value in data.items():
                key = _from_json(key_type, key)
                value = _from_json(val_type, value)
                instance[key] = value
        else:
            raise Exception(
                'Trying to deserialize an unsupported type: {cls._name}')

    # Handle everything else by first instantiating the class, then adding
    # all of the sub-elements, recursively calling from_json on them.
    else:
        instance: cls = cls()
        for field, field_type in annotations.items():
            value = data.get(field)
            setattr(instance, field, _from_json(field_type, value))

    return instance


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
