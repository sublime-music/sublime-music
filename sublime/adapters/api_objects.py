"""
Defines the objects that are returned by adapter methods.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional


@dataclass(frozen=True)
class Song:
    id: str


@dataclass(frozen=True)
class Playlist:
    id: str
    name: str
    songCount: Optional[int] = None  # TODO rename
    duration: Optional[timedelta] = None
    created: Optional[datetime] = None
    changed: Optional[datetime] = None
    comment: Optional[str] = None
    owner: Optional[str] = None
    public: Optional[bool] = None
    coverArt: Optional[str] = None  # TODO rename


@dataclass(frozen=True)
class PlaylistDetails():
    id: str
    name: str
    songCount: int  # TODO rename
    duration: timedelta
    created: Optional[datetime] = None
    changed: Optional[datetime] = None
    comment: Optional[str] = None
    owner: Optional[str] = None
    public: Optional[bool] = None
    coverArt: Optional[str] = None  # TODO rename
    songs: List[Song] = field(default_factory=list)
