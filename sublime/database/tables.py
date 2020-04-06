import sqlite3
import typing
from datetime import datetime
from typing import Optional

song_table = '''
CREATE TABLE songs
(
    id TEXT NOT NULL UNIQUE PRIMARY KEY,
    parent TEXT,
    title TEXT,
    track INTEGER,
    year INTEGER,
    genre TEXT,
    cover_art TEXT,
    size INTEGER,
    duration INTEGER,
    path TEXT
)
'''

conn = sqlite3.connect(':memory:')

c = conn.cursor()
c.execute(song_table)
c.execute('''INSERT INTO songs (id, parent, title, year, genre)
                        VALUES ('1', 'ohea', 'Awake My Soul', 2019, 'Contemporary Christian')''')
c.execute('''INSERT INTO songs (id, parent, title, year, genre)
                        VALUES ('2', 'ohea', 'Way Maker', 2019, 'Contemporary Christian')''')
conn.commit()
c.execute('''SELECT * FROM songs''')
print(c.fetchall())
conn.close()

table_definitions = (
    (
        'playlist',
        {
            'id': int,
            'name': str,
            'comment': Optional[str],
            'owner': Optional[str],
            'public': Optional[bool],
            'song_count': int,
            'duration': int,
            'created': datetime,
            'changed': datetime,
            'cover_art': Optional[str],
        },
    ),
    (
        'song',
        {
            'id': int,
            'parent': Optional[str],
            'title': str,
        },
    ),
    (
        'playlist_song_xref',
        {
            'playlist_id': int,
            'song_id': int,
            'position': int,
        },
    ),
)

python_to_sql_type = {
    int: 'INTEGER',
    float: 'REAL',
    bool: 'INTEGER',
    datetime: 'TIMESTAMP',
    str: 'TEXT',
    bytes: 'BLOB',
}

for name, fields in table_definitions:
    field_defs = []
    for field, field_type in fields.items():
        if type(field_type) == tuple:
            print(field_type)
        elif type(field_type) is typing._GenericAlias:  # type: ignore
            sql_type = python_to_sql_type.get(field_type.__args__[0])
            constraints = ''
        else:
            sql_type = python_to_sql_type.get(field_type)
            constraints = ' NOT NULL'

        field_defs.append(f'{field} {sql_type}{constraints}')

    print(f'''
    CREATE TABLE {name}
    ({','.join(field_defs)})
    ''')

'''

    id: str
    value: str
    parent: Optional[str]
    isDir: bool
    title: str
    album: Optional[str]
    artist: Optional[str]
    track: Optional[int]
    year: Optional[int]
    genre: Optional[str]
    coverArt: Optional[str]
    size: Optional[int]
    contentType: Optional[str]
    suffix: Optional[str]
    transcodedContentType: Optional[str]
    transcodedSuffix: Optional[str]
    duration: Optional[int]
    bitRate: Optional[int]
    path: Optional[str]
    userRating: Optional[UserRating]
    averageRating: Optional[AverageRating]
    playCount: Optional[int]
    discNumber: Optional[int]
    created: Optional[datetime]
    starred: Optional[datetime]
    albumId: Optional[str]
    artistId: Optional[str]
    type: Optional[MediaType]
'''
