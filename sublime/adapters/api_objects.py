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


@dataclass(frozen=True)
class PlaylistDetails(Playlist):
    songCount: int
    duration: timedelta
    created: Optional[datetime] = None
    changed: Optional[datetime] = None
    comment: Optional[str] = None
    owner: Optional[str] = None
    public: Optional[bool] = None
    coverArt: Optional[str] = None
    songs: List[Song] = field(default_factory=list)
