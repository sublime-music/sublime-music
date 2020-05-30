"""
Defines the objects that are returned by adapter methods.
"""
import abc
import logging
from datetime import datetime, timedelta
from functools import lru_cache, partial
from typing import (
    Any,
    Callable,
    cast,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

from fuzzywuzzy import fuzz


class Genre(abc.ABC):
    name: str
    song_count: Optional[int]
    album_count: Optional[int]


class Album(abc.ABC):
    """
    The ``id`` field is optional, because there are some situations where an adapter
    (such as Subsonic) sends an album name, but not an album ID.
    """

    name: str
    id: Optional[str]
    artist: Optional["Artist"]
    cover_art: Optional[str]
    created: Optional[datetime]
    duration: Optional[timedelta]
    genre: Optional[Genre]
    play_count: Optional[int]
    song_count: Optional[int]
    songs: Optional[Sequence["Song"]]
    starred: Optional[datetime]
    year: Optional[int]


class Artist(abc.ABC):
    """
    The ``id`` field is optional, because there are some situations where an adapter
    (such as Subsonic) sends an artist name, but not an artist ID. This especially
    happens when there are multiple artists.
    """

    name: str
    id: Optional[str]
    album_count: Optional[int]
    artist_image_url: Optional[str]
    starred: Optional[datetime]
    albums: Optional[Sequence[Album]]

    similar_artists: Optional[Sequence["Artist"]] = None
    biography: Optional[str] = None
    music_brainz_id: Optional[str] = None
    last_fm_url: Optional[str] = None


class Directory(abc.ABC):
    """
    The special directory with ``name`` and ``id`` should be used to indicate the
    top-level directory.
    """

    id: str
    name: Optional[str]
    parent_id: Optional[str]
    children: Sequence[Union["Directory", "Song"]]


class Song(abc.ABC):
    id: str
    title: str
    path: Optional[str]
    parent_id: Optional[str]
    duration: Optional[timedelta]

    album: Optional[Album]
    artist: Optional[Artist]
    genre: Optional[Genre]

    track: Optional[int]
    disc_number: Optional[int]
    year: Optional[int]
    cover_art: Optional[str]
    size: Optional[int]
    user_rating: Optional[int]
    starred: Optional[datetime]


class Playlist(abc.ABC):
    id: str
    name: str
    song_count: Optional[int]
    duration: Optional[timedelta]
    songs: Sequence[Song]
    created: Optional[datetime]
    changed: Optional[datetime]
    comment: Optional[str]
    owner: Optional[str]
    public: Optional[bool]
    cover_art: Optional[str]


class PlayQueue(abc.ABC):
    songs: Sequence[Song]
    position: timedelta
    username: Optional[str]
    changed: Optional[datetime]
    changed_by: Optional[str]
    value: Optional[str]
    current_index: Optional[int]


@lru_cache(maxsize=8192)
def similarity_ratio(query: str, string: str) -> int:
    """
    Return the :class:`fuzzywuzzy.fuzz.partial_ratio` between the ``query`` and
    the given ``string``.

    This ends up being called quite a lot, so the result is cached in an LRU
    cache using :class:`functools.lru_cache`.

    :param query: the query string
    :param string: the string to compare to the query string
    """
    return fuzz.partial_ratio(query, string)


class SearchResult:
    """
    An object representing the aggregate results of a search which can include
    both server and local results.
    """

    def __init__(self, query: str = None):
        self.query = query
        self._artists: Dict[str, Artist] = {}
        self._albums: Dict[str, Album] = {}
        self._songs: Dict[str, Song] = {}
        self._playlists: Dict[str, Playlist] = {}

    def add_results(self, result_type: str, results: Iterable):
        """Adds the ``results`` to the ``_result_type`` set."""
        if results is None:
            return

        member = f"_{result_type}"
        cast(Dict[str, Any], getattr(self, member)).update({r.id: r for r in results})

    def update(self, other: "SearchResult"):
        assert self.query == other.query
        self._artists.update(other._artists)
        self._albums.update(other._albums)
        self._songs.update(other._songs)
        self._playlists.update(other._playlists)

    _S = TypeVar("_S")

    def _to_result(
        self, it: Dict[str, _S], transform: Callable[[_S], Tuple[Optional[str], ...]],
    ) -> List[_S]:
        assert self.query
        all_results = sorted(
            (
                (
                    max(
                        partial(similarity_ratio, self.query.lower())(t.lower())
                        for t in transform(x)
                        if t is not None
                    ),
                    x,
                )
                for x in it.values()
            ),
            key=lambda rx: rx[0],
            reverse=True,
        )
        result: List[SearchResult._S] = []
        for ratio, x in all_results:
            if ratio >= 60 and len(result) < 20:
                result.append(x)
            else:
                # No use going on, all the rest are less.
                break

        logging.debug(similarity_ratio.cache_info())
        return result

    @property
    def artists(self) -> List[Artist]:
        return self._to_result(self._artists, lambda a: (a.name,))

    @property
    def albums(self) -> List[Album]:
        return self._to_result(
            self._albums, lambda a: (a.name, a.artist.name if a.artist else None)
        )

    @property
    def songs(self) -> List[Song]:
        return self._to_result(
            self._songs, lambda s: (s.title, s.artist.name if s.artist else None)
        )

    @property
    def playlists(self) -> List[Playlist]:
        return self._to_result(self._playlists, lambda p: (p.name,))
