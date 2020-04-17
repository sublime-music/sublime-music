"""
Defines the objects that are returned by adapter methods.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional


@dataclass
class Playlist:
    id: str
    name: str
    songCount: Optional[int]
    duration: Optional[timedelta]
    created: Optional[datetime]
    changed: Optional[datetime]

    allowedUser: List[str] = field(default_factory=list)
    value: Optional[str] = None
    comment: Optional[str] = None
    owner: Optional[str] = None
    public: Optional[bool] = None
    coverArt: Optional[str] = None


@dataclass
class PlaylistDetails:
    pass
