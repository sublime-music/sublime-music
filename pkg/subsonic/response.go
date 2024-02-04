package subsonic

// ResponseStatus is the status of a Subsonic response.
//
// Subsonic 1.16.1 Definition:
//
//	<xs:simpleType name="ResponseStatus">
//	    <xs:restriction base="xs:string">
//	        <xs:enumeration value="ok"/>
//	        <xs:enumeration value="failed"/>
//	    </xs:restriction>
//	</xs:simpleType>
type SubsonicResponseStatus string

const (
	SubsonicResponseStatusOk     SubsonicResponseStatus = "ok"
	SubsonicResponseStatusFailed SubsonicResponseStatus = "failed"
)

// SubsonicResponse is the top-level response object from the Subsonic API.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Response">
//	    <xs:choice minOccurs="0" maxOccurs="1">
//	        <xs:element name="musicFolders" type="sub:MusicFolders" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="indexes" type="sub:Indexes" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="directory" type="sub:Directory" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="genres" type="sub:Genres" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="artists" type="sub:ArtistsID3" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="artist" type="sub:ArtistWithAlbumsID3" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="album" type="sub:AlbumWithSongsID3" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="song" type="sub:Child" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="videos" type="sub:Videos" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="videoInfo" type="sub:VideoInfo" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="nowPlaying" type="sub:NowPlaying" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="searchResult" type="sub:SearchResult" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="searchResult2" type="sub:SearchResult2" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="searchResult3" type="sub:SearchResult3" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="playlists" type="sub:Playlists" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="playlist" type="sub:PlaylistWithSongs" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="jukeboxStatus" type="sub:JukeboxStatus" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="jukeboxPlaylist" type="sub:JukeboxPlaylist" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="license" type="sub:License" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="users" type="sub:Users" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="user" type="sub:User" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="chatMessages" type="sub:ChatMessages" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="albumList" type="sub:AlbumList" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="albumList2" type="sub:AlbumList2" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="randomSongs" type="sub:Songs" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="songsByGenre" type="sub:Songs" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="lyrics" type="sub:Lyrics" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="podcasts" type="sub:Podcasts" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="newestPodcasts" type="sub:NewestPodcasts" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="internetRadioStations" type="sub:InternetRadioStations" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="bookmarks" type="sub:Bookmarks" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="playQueue" type="sub:PlayQueue" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="shares" type="sub:Shares" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="starred" type="sub:Starred" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="starred2" type="sub:Starred2" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="albumInfo" type="sub:AlbumInfo" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="artistInfo" type="sub:ArtistInfo" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="artistInfo2" type="sub:ArtistInfo2" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="similarSongs" type="sub:SimilarSongs" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="similarSongs2" type="sub:SimilarSongs2" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="topSongs" type="sub:TopSongs" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="scanStatus" type="sub:ScanStatus" minOccurs="1" maxOccurs="1"/>
//	        <xs:element name="error" type="sub:Error" minOccurs="1" maxOccurs="1"/>
//	    </xs:choice>
//	    <xs:attribute name="status" type="sub:ResponseStatus" use="required"/>
//	    <xs:attribute name="version" type="sub:Version" use="required"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/subsonic-response/
type SubsonicResponse struct {
	Status  string `json:"status"`
	Version string `json:"version"`

	MusicFolders          *MusicFolders          `json:"musicFolders"`
	Indexes               *Indexes               `json:"indexes"`
	Directory             *Directory             `json:"directory"`
	Genres                *Genres                `json:"genres"`
	Artists               *ArtistsID3            `json:"artists"`
	Artist                *Artist                `json:"artist"`
	Album                 *AlbumID3              `json:"album"`
	Song                  *Child                 `json:"song"`
	Videos                *Videos                `json:"videos"`
	VideoInfo             *VideoInfo             `json:"videoInfo"`
	NowPlaying            *NowPlaying            `json:"nowPlaying"`
	SearchResult          *SearchResult          `json:"searchResult"`
	SearchResult2         *SearchResult2         `json:"searchResult2"`
	SearchResult3         *SearchResult3         `json:"searchResult3"`
	Playlists             *Playlists             `json:"playlists"`
	Playlist              *Playlist              `json:"playlist"`
	JukeboxStatus         *JukeboxStatus         `json:"jukeboxStatus"`
	JukeboxPlaylist       *JukeboxPlaylist       `json:"jukeboxPlaylist"`
	License               *License               `json:"license"`
	Users                 *Users                 `json:"users"`
	User                  *User                  `json:"user"`
	ChatMessages          *ChatMessages          `json:"chatMessages"`
	AlbumList             *AlbumList             `json:"albumList"`
	AlbumList2            *AlbumList2            `json:"albumList2"`
	RandomSongs           *Songs                 `json:"randomSongs"`
	SongsByGenre          *Songs                 `json:"songsByGenre"`
	Lyrics                *Lyrics                `json:"lyrics"`
	Podcasts              *Podcasts              `json:"podcasts"`
	NewestPodcasts        *NewestPodcasts        `json:"newestPodcasts"`
	InternetRadioStations *InternetRadioStations `json:"internetRadioStations"`
	Bookmarks             *Bookmarks             `json:"bookmarks"`
	PlayQueue             *PlayQueue             `json:"playQueue"`
	Shares                *Shares                `json:"shares"`
	Starred               *Starred               `json:"starred"`
	Starred2              *Starred2              `json:"starred2"`
	AlbumInfo             *AlbumInfo             `json:"albumInfo"`
	ArtistInfo            *ArtistInfo            `json:"artistInfo"`
	ArtistInfo2           *ArtistInfo2           `json:"artistInfo2"`
	SimilarSongs          *SimilarSongs          `json:"similarSongs"`
	SimilarSongs2         *SimilarSongs2         `json:"similarSongs2"`
	TopSongs              *TopSongs              `json:"topSongs"`
	ScanStatus            *ScanStatus            `json:"scanStatus"`
	Error                 *Error                 `json:"error,omitempty"`

	Type                   string                  `json:"type,omitempty"`                   // OpenSubsonic addition
	ServerVersion          string                  `json:"serverVersion,omitempty"`          // OpenSubsonic addition
	OpenSubsonic           bool                    `json:"openSubsonic,omitempty"`           // OpenSubsonic addition
	OpenSubsonicExtensions []OpenSubsonicExtension `json:"openSubsonicExtensions,omitempty"` // OpenSubsonic addition
}

// Response is a Subsonic root response object.
//
// Subsonic 1.16.1 Definition:
//
//	<xs:element name="subsonic-response" type="sub:Response"/>
type Response struct {
	SubsonicResponse *SubsonicResponse `json:"subsonic-response,omitempty"`
}
