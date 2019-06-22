from datetime import datetime
from typing import List
from enum import Enum

from .api_object import APIObject


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


class MediaType(APIObject, Enum):
    pass


class Child(APIObject):
    id: str
    parent: str
    isDir: bool
    title: str
    album: str
    artist: str
    track: int
    year: int
    genre: str
    coverArt: str
    size: int
    contentType: str
    suffix: str
    transcodedContentType: str
    transcodedSuffix: str
    duration: int
    bitRate: int
    path: str
    isVideo: bool
    userRating: UserRating
    averageRating: AverageRating
    playCount: int
    discNumber: int
    created: datetime
    starred: datetime
    albumId: str
    artistId: str
    type: MediaType
    bookmarkPosition: int
    originalWidth: int
    originalHeight: int


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

    song: List[Child]


class AlbumID3(APIObject):
    id: str
    name: str
    artist: str
    artistId: str
    coverArt: str
    songCount: int
    duration: int
    playCount: int
    created: datetime
    starred: datetime
    year: int
    genre: str


class AlbumWithSongsID3(APIObject):
    id: str
    name: str
    artist: str
    artistId: str
    coverArt: str
    songCount: int
    duration: int
    playCount: int
    created: datetime
    starred: datetime
    year: int
    genre: str

    song: List[Child]


class Artist(APIObject):
    id: str
    name: str
    artistImageUrl: str
    starred: datetime
    userRating: UserRating
    averageRating: AverageRating


class ArtistID3(APIObject):
    id: str
    name: str
    coverArt: str
    artistImageUrl: str
    albumCount: int
    starred: datetime


class ArtistWithAlbumsID3(APIObject):
    id: str
    name: str
    coverArt: str
    artistImageUrl: str
    albumCount: int
    starred: datetime
    album: List[AlbumID3]


class Index(APIObject):
    name: str
    artist: List[Artist]


class IndexID3(APIObject):
    name: str
    artist: List[ArtistID3]


class Indexes(APIObject):
    lastModified: int
    ignoredArticles: str
    index: List[Index]
    shortcut: List[Artist]
    child: List[Child]


class Directory(APIObject):
    id: str
    parent: str
    name: str
    starred: datetime
    userRating: UserRating
    averageRating: AverageRating
    playCount: int

    child: List[Child]


class Genre(APIObject):
    songCount: int
    albumCount: int


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


class Captions(APIObject):
    id: str
    name: str


class AudioTrack(APIObject):
    id: str
    name: str
    languageCode: str


class VideoConversion(APIObject):
    id: str
    bitRate: int
    audioTrackId: int


class VideoInfo(APIObject):
    id: str
    captions: List[Captions]
    audioTrack: List[AudioTrack]
    conversion: List[VideoConversion]


class ArtistsID3(APIObject):
    ignoredArticles: str
    index: List[IndexID3]


class MusicFolders(APIObject):
    musicFolder: List[MusicFolder]


class Genres(APIObject):
    genre: List[Genre]


class Artists(APIObject):
    index: List[Index]


class Videos(APIObject):
    video: List[Child]


class SimilarSongs(APIObject):
    song: List[Child]


class TopSongs(APIObject):
    song: List[Child]


class AlbumList(APIObject):
    album: List[Album]


class ResponseStatus(APIObject, Enum):
    ok = "ok"
    failed = "failed"


class SubsonicResponse(APIObject):
    # On every Subsonic Response
    status: ResponseStatus
    version: str

    # One of these will exist on each SubsonicResponse
    album: AlbumWithSongsID3
    albumInfo: AlbumInfo
    albumList: AlbumList
    albumList2: AlbumList2
    artist: ArtistWithAlbumsID3
    artistInfo: ArtistInfo
    artistInfo2: ArtistInfo2
    artists: ArtistsID3
    bookmarks: Bookmarks
    chatMessages: ChatMessages
    directory: Directory
    error: Error
    genres: Genres
    indexes: Indexes
    internetRadioStations: InternetRadioStations
    jukeboxPlaylist: JukeboxPlaylist
    jukeboxStatus: JukeboxStatus
    license: License
    lyrics: Lyrics
    musicFolders: MusicFolders
    newestPodcasts: NewestPodcasts
    nowPlaying: NowPlaying
    playlist: PlaylistWithSongs
    playlists: Playlists
    playQueue: PlayQueue
    podcasts: Podcasts
    randomSongs: Songs
    scanStatus: ScanStatus
    searchResult: SearchResult
    searchResult2: SearchResult2
    searchResult3: SearchResult3
    shares: Shares
    similarSongs: SimilarSongs
    similarSongs2: SimilarSongs2
    song: Child
    songsByGenre: Songs
    starred: Starred
    starred2: Starred2
    topSongs: TopSongs
    user: User
    users: Users
    videos: Videos
    videoInfo: VideoInfo
