package subsonic

import (
	"time"

	"go.mau.fi/util/jsontime"
)

// This file is organized in the same order as the definitions in
// subsonic-rest-api-1.16.1.xsd which can be found here:
// https://www.subsonic.org/pages/inc/api/schema/subsonic-rest-api-1.16.1.xsd.

// MusicFolders is a list of [MusicFolder] objects.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="MusicFolders">
//	    <xs:sequence>
//	        <xs:element name="musicFolder" type="sub:MusicFolder" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/musicfolders/
type MusicFolders struct {
	MusicFolder []MusicFolder `json:"musicFolder,omitempty"`
}

// MusicFolder is a music folder.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="MusicFolder">
//	    <xs:attribute name="id" type="xs:int" use="required"/>
//	    <xs:attribute name="name" type="xs:string" use="optional"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/musicfolder/
type MusicFolder struct {
	ID   SubsonicID `json:"id"`
	Name string     `json:"name,omitempty"`
}

// Indexes is an indexed list of artists.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Indexes">
//	    <xs:sequence>
//	        <xs:element name="shortcut" type="sub:Artist" minOccurs="0" maxOccurs="unbounded"/>
//	        <xs:element name="index" type="sub:Index" minOccurs="0" maxOccurs="unbounded"/>
//	        <xs:element name="child" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/> <!-- Added in 1.7.0 -->
//	    </xs:sequence>
//	    <xs:attribute name="lastModified" type="xs:long" use="required"/>
//	    <xs:attribute name="ignoredArticles" type="xs:string" use="required"/> <!-- Added in 1.10.0 -->
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/indexes/
type Indexes struct {
	Shortcut        []Artist           `json:"shortcut,omitempty"`
	Index           []Index            `json:"index,omitempty"`
	Child           []Child            `json:"child,omitempty"` // Added in 1.7.0
	LastModified    jsontime.UnixMilli `json:"lastModified"`
	IgnoredArticles IgnoredArticles    `json:"ignoredArticles,omitempty"` // Added in 1.10.0
}

// Index is an indexed list of artists.
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Index">
//	    <xs:sequence>
//	        <xs:element name="artist" type="sub:Artist" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	    <xs:attribute name="name" type="xs:string" use="required"/>
//	</xs:complexType>
type Index struct {
	Name   string   `json:"name"`
	Artist []Artist `json:"artist,omitempty"`
}

// Artist is an artist.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Artist">
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	    <xs:attribute name="name" type="xs:string" use="required"/>
//	    <xs:attribute name="artistImageUrl" type="xs:string" use="optional"/>  <!-- Added in 1.16.1 -->
//	    <xs:attribute name="starred" type="xs:dateTime" use="optional"/> <!-- Added in 1.10.1 -->
//	    <xs:attribute name="userRating" type="sub:UserRating" use="optional"/>  <!-- Added in 1.13.0 -->
//	    <xs:attribute name="averageRating" type="sub:AverageRating" use="optional"/>  <!-- Added in 1.13.0 -->
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/artist/
type Artist struct {
	ID             SubsonicID `json:"id"`
	Name           string     `json:"name"`
	ArtistImageURL string     `json:"artistImageUrl,omitempty"` // Added in 1.16.1
	Starred        *time.Time `json:"starred,omitempty"`        // Added in 1.10.1
	UserRating     int        `json:"userRating,omitempty"`     // Added in 1.13.0
	AverageRating  float64    `json:"averageRating,omitempty"`  // Added in 1.13.0
}

// Genre is a list of genres.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Genres">
//	    <xs:sequence>
//	        <xs:element name="genre" type="sub:Genre" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/genres/
type Genres struct {
	Genre []Genre `json:"genre,omitempty"`
}

// Genre is a genre.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Genre" mixed="true">
//	    <xs:attribute name="songCount" type="xs:int" use="required"/>  <!-- Added in 1.10.2 -->
//	    <xs:attribute name="albumCount" type="xs:int" use="required"/> <!-- Added in 1.10.2 -->
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/genre/
type Genre struct {
	Value      string `json:"value"`
	SongCount  int    `json:"songCount"`
	AlbumCount int    `json:"albumCount"`
}

// ArtistsID3 is a list of ID3 artists.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="ArtistsID3">
//	    <xs:sequence>
//	        <xs:element name="index" type="sub:IndexID3" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	    <xs:attribute name="ignoredArticles" type="xs:string" use="required"/> <!-- Added in 1.10.0 -->
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/artistsid3/
type ArtistsID3 struct {
	IgnoredArticles IgnoredArticles `json:"ignoredArticles,omitempty"`
	Index           []IndexID3      `json:"index,omitempty"`
}

// IndexID3 is an indexed list of ID3 artists.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="IndexID3">
//	    <xs:sequence>
//	        <xs:element name="artist" type="sub:ArtistID3" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	    <xs:attribute name="name" type="xs:string" use="required"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/indexeid3/
type IndexID3 struct {
	Name   string      `json:"name"`
	Artist []ArtistID3 `json:"artist"`
}

// ArtistID3 is an artist from ID3 tags.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="ArtistID3">
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	    <xs:attribute name="name" type="xs:string" use="required"/>
//	    <xs:attribute name="coverArt" type="xs:string" use="optional"/>
//	    <xs:attribute name="artistImageUrl" type="xs:string" use="optional"/>  <!-- Added in 1.16.1 -->
//	    <xs:attribute name="albumCount" type="xs:int" use="required"/>
//	    <xs:attribute name="starred" type="xs:dateTime" use="optional"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/artistid3/
type ArtistID3 struct {
	ID             SubsonicID `json:"id"`
	Name           string     `json:"name"`
	CoverArt       string     `json:"coverArt,omitempty"`
	ArtistImageURL string     `json:"artistImageUrl,omitempty"` // Added in 1.16.1
	AlbumCount     int        `json:"albumCount,omitempty"`
	Starred        *time.Time `json:"starred,omitempty"`
	MusicBrainzID  string     `json:"musicBrainzId,omitempty"` // OpenSubsonic addition
	SortName       string     `json:"sortName,omitempty"`      // OpenSubsonic addition
	Roles          []string   `json:"roles,omitempty"`         // OpenSubsonic addition
}

// ArtistWithAlbumsID3 is an artist from ID3 tags with their albums.
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="ArtistWithAlbumsID3">
//	    <xs:complexContent>
//	        <xs:extension base="sub:ArtistID3">
//	            <xs:sequence>
//	                <xs:element name="album" type="sub:AlbumID3" minOccurs="0" maxOccurs="unbounded"/>
//	            </xs:sequence>
//	        </xs:extension>
//	    </xs:complexContent>
//	</xs:complexType>
type ArtistWithAlbumsID3 struct {
	ArtistID3
	Album []AlbumID3 `json:"album"`
}

// AlbumID3 is an album from ID3 tags.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="AlbumID3">
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	    <xs:attribute name="name" type="xs:string" use="required"/>
//	    <xs:attribute name="artist" type="xs:string" use="optional"/>
//	    <xs:attribute name="artistId" type="xs:string" use="optional"/>
//	    <xs:attribute name="coverArt" type="xs:string" use="optional"/>
//	    <xs:attribute name="songCount" type="xs:int" use="required"/>
//	    <xs:attribute name="duration" type="xs:int" use="required"/>
//	    <xs:attribute name="playCount" type="xs:long" use="optional"/>  <!-- Added in 1.14.0 -->
//	    <xs:attribute name="created" type="xs:dateTime" use="required"/>
//	    <xs:attribute name="starred" type="xs:dateTime" use="optional"/>
//	    <xs:attribute name="year" type="xs:int" use="optional"/>     <!-- Added in 1.10.1 -->
//	    <xs:attribute name="genre" type="xs:string" use="optional"/> <!-- Added in 1.10.1 -->
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/albumid3/
type AlbumID3 struct {
	ID                  SubsonicID    `json:"id"`
	Name                string        `json:"name"`
	Artist              string        `json:"artist"`
	ArtistID            SubsonicID    `json:"artistId"`
	CoverArt            string        `json:"coverArt,omitempty"`
	SongCount           int           `json:"songCount"`
	Duration            int           `json:"duration"`
	PlayCount           int64         `json:"playCount,omitempty"` // Added in 1.14.0
	Created             time.Time     `json:"created,omitempty"`
	Starred             *time.Time    `json:"starred,omitempty"`
	Year                int           `json:"year,omitempty"`                // Added in 1.10.1
	Genre               string        `json:"genre,omitempty"`               // Added in 1.10.1
	Played              *time.Time    `json:"played,omitempty"`              // OpenSubsonic addition
	UserRating          int           `json:"userRating,omitempty"`          //OpenSubsonic addition
	RecordLabels        []RecordLabel `json:"recordLabels,omitempty"`        //OpenSubsonic addition
	MusicBrainzID       string        `json:"musicBrainzId,omitempty"`       //OpenSubsonic addition
	Genres              []ItemGenre   `json:"genres,omitempty"`              //OpenSubsonic addition
	Artists             []ArtistID3   `json:"artists,omitempty"`             //OpenSubsonic addition
	DisplayArtist       string        `json:"displayArtist,omitempty"`       //OpenSubsonic addition
	ReleaseTypes        []string      `json:"releaseTypes,omitempty"`        //OpenSubsonic addition
	Moods               []string      `json:"moods,omitempty"`               //OpenSubsonic addition
	SortName            string        `json:"sortName,omitempty"`            //OpenSubsonic addition
	OriginalReleaseDate ItemDate      `json:"originalReleaseDate,omitempty"` //OpenSubsonic addition
	IsCompilation       bool          `json:"isCompilation,omitempty"`       //OpenSubsonic addition
	DiscTitles          []DiscTitle   `json:"discTitles,omitempty"`          //OpenSubsonic addition
}

// AlbumID3WithSongs is an album with songs.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="AlbumWithSongsID3">
//	    <xs:complexContent>
//	        <xs:extension base="sub:AlbumID3">
//	            <xs:sequence>
//	                <xs:element name="song" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	            </xs:sequence>
//	        </xs:extension>
//	    </xs:complexContent>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/albumid3withsongs/
type AlbumID3WithSongs struct {
	AlbumID3
	Song []Child `json:"song,omitempty"`
}

// Videos is a list of videos.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Videos">
//	    <xs:sequence>
//	        <xs:element name="video" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/videos/
type Videos struct {
	Video []Child `json:"video,omitempty"`
}

// VideoInfo is the information about a video.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="VideoInfo">
//	    <xs:sequence>
//	        <xs:element name="captions" type="sub:Captions" minOccurs="0" maxOccurs="unbounded"/>
//	        <xs:element name="audioTrack" type="sub:AudioTrack" minOccurs="0" maxOccurs="unbounded"/>
//	        <xs:element name="conversion" type="sub:VideoConversion" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/videoinfo/
type VideoInfo struct {
	Captions   []Captions        `json:"captions,omitempty"`
	AudioTrack []AudioTrack      `json:"audioTrack,omitempty"`
	Conversion []VideoConversion `json:"conversion,omitempty"`
	ID         SubsonicID        `json:"id"`
}

// Captions is the captions for a video
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Captions">
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	    <xs:attribute name="name" type="xs:string" use="optional"/>
//	</xs:complexType>
type Captions struct {
	ID   SubsonicID `json:"id"`
	Name string     `json:"name,omitempty"`
}

// AudioTrack is an audio track for a video.
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="AudioTrack">
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	    <xs:attribute name="name" type="xs:string" use="optional"/>
//	    <xs:attribute name="languageCode" type="xs:string" use="optional"/>
//	</xs:complexType>
type AudioTrack struct {
	ID           SubsonicID `json:"id"`
	Name         string     `json:"name,omitempty"`
	LanguageCode string     `json:"languageCode,omitempty"`
}

// VideoConversion is a converted video.
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="VideoConversion">
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	    <xs:attribute name="bitRate" type="xs:int" use="optional"/> <!-- In Kbps -->
//	    <xs:attribute name="audioTrackId" type="xs:int" use="optional"/>
//	</xs:complexType>
type VideoConversion struct {
	ID           SubsonicID `json:"id"`
	BitRate      int        `json:"bitRate,omitempty"` // In Kbps
	AudioTrackID SubsonicID `json:"audioTrackId,omitempty"`
}

// Directory is a directory.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Directory">
//	    <xs:sequence>
//	        <xs:element name="child" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	    <xs:attribute name="parent" type="xs:string" use="optional"/>
//	    <xs:attribute name="name" type="xs:string" use="required"/>
//	    <xs:attribute name="starred" type="xs:dateTime" use="optional"/> <!-- Added in 1.10.1 -->
//	    <xs:attribute name="userRating" type="sub:UserRating" use="optional"/>  <!-- Added in 1.13.0 -->
//	    <xs:attribute name="averageRating" type="sub:AverageRating" use="optional"/>  <!-- Added in 1.13.0 -->
//	    <xs:attribute name="playCount" type="xs:long" use="optional"/>  <!-- Added in 1.14.0 -->
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/directory/
type Directory struct {
	Child         []Child    `json:"child,omitempty"`
	ID            SubsonicID `json:"id"`
	Parent        SubsonicID `json:"parent,omitempty"`
	Name          string     `json:"name"`
	Starred       *time.Time `json:"starred,omitempty"`       // Added in 1.10.1
	UserRating    int        `json:"userRating,omitempty"`    // Added in 1.13.0
	AverageRating float64    `json:"averageRating,omitempty"` // Added in 1.13.0
	PlayCount     int64      `json:"playCount,omitempty"`     // Added in 1.14.0
}

// Child is a media.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Child">
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	    <xs:attribute name="parent" type="xs:string" use="optional"/>
//	    <xs:attribute name="isDir" type="xs:boolean" use="required"/>
//	    <xs:attribute name="title" type="xs:string" use="required"/>
//	    <xs:attribute name="album" type="xs:string" use="optional"/>
//	    <xs:attribute name="artist" type="xs:string" use="optional"/>
//	    <xs:attribute name="track" type="xs:int" use="optional"/>
//	    <xs:attribute name="year" type="xs:int" use="optional"/>
//	    <xs:attribute name="genre" type="xs:string" use="optional"/>
//	    <xs:attribute name="coverArt" type="xs:string" use="optional"/>
//	    <xs:attribute name="size" type="xs:long" use="optional"/>
//	    <xs:attribute name="contentType" type="xs:string" use="optional"/>
//	    <xs:attribute name="suffix" type="xs:string" use="optional"/>
//	    <xs:attribute name="transcodedContentType" type="xs:string" use="optional"/>
//	    <xs:attribute name="transcodedSuffix" type="xs:string" use="optional"/>
//	    <xs:attribute name="duration" type="xs:int" use="optional"/>
//	    <xs:attribute name="bitRate" type="xs:int" use="optional"/>
//	    <xs:attribute name="path" type="xs:string" use="optional"/>
//	    <xs:attribute name="isVideo" type="xs:boolean" use="optional"/>  <!-- Added in 1.4.1 -->
//	    <xs:attribute name="userRating" type="sub:UserRating" use="optional"/>  <!-- Added in 1.6.0 -->
//	    <xs:attribute name="averageRating" type="sub:AverageRating" use="optional"/>  <!-- Added in 1.6.0 -->
//	    <xs:attribute name="playCount" type="xs:long" use="optional"/>  <!-- Added in 1.14.0 -->
//	    <xs:attribute name="discNumber" type="xs:int" use="optional"/>  <!-- Added in 1.8.0 -->
//	    <xs:attribute name="created" type="xs:dateTime" use="optional"/>  <!-- Added in 1.8.0 -->
//	    <xs:attribute name="starred" type="xs:dateTime" use="optional"/>  <!-- Added in 1.8.0 -->
//	    <xs:attribute name="albumId" type="xs:string" use="optional"/>  <!-- Added in 1.8.0 -->
//	    <xs:attribute name="artistId" type="xs:string" use="optional"/>  <!-- Added in 1.8.0 -->
//	    <xs:attribute name="type" type="sub:MediaType" use="optional"/>  <!-- Added in 1.8.0 -->
//	    <xs:attribute name="bookmarkPosition" type="xs:long" use="optional"/>  <!-- In millis. Added in 1.10.1 -->
//	    <xs:attribute name="originalWidth" type="xs:int" use="optional"/>  <!-- Added in 1.13.0 -->
//	    <xs:attribute name="originalHeight" type="xs:int" use="optional"/>  <!-- Added in 1.13.0 -->
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/child/
type Child struct {
	ID                    SubsonicID         `json:"id"`
	Parent                SubsonicID         `json:"parent,omitempty"`
	IsDir                 bool               `json:"isDir"`
	Title                 string             `json:"title"`
	Album                 string             `json:"album,omitempty"`
	Artist                string             `json:"artist,omitempty"`
	Track                 int                `json:"track,omitempty"`
	Year                  int                `json:"year,omitempty"`
	Genre                 string             `json:"genre,omitempty"`
	CoverArt              string             `json:"coverArt,omitempty"`
	Size                  int64              `json:"size,omitempty"`
	ContentType           string             `json:"contentType,omitempty"`
	Suffix                string             `json:"suffix,omitempty"`
	TranscodedContentType string             `json:"transcodedContentType,omitempty"`
	TranscodedSuffix      string             `json:"transcodedSuffix,omitempty"`
	Duration              int                `json:"duration,omitempty"`
	BitRate               int                `json:"bitRate,omitempty"`
	Path                  string             `json:"path,omitempty"`
	IsVideo               bool               `json:"isVideo,omitempty"`       // Added 1.4.1
	UserRating            int                `json:"userRating,omitempty"`    // Added in 1.6.0
	AverageRating         float64            `json:"averageRating,omitempty"` // Added in 1.6.0
	PlayCount             int64              `json:"playCount,omitempty"`     // Added in 1.14.0
	DiscNumber            int                `json:"discNumber,omitempty"`    // Added in 1.8.0
	Created               *time.Time         `json:"created,omitempty"`       // Added in 1.8.0
	Starred               *time.Time         `json:"starred,omitempty"`       // Added in 1.8.0
	AlbumID               SubsonicID         `json:"albumId,omitempty"`       // Added in 1.8.0
	ArtistID              SubsonicID         `json:"artistId,omitempty"`      // Added in 1.8.0
	Type                  MediaType          `json:"type,omitempty"`          // Added in 1.8.0
	MediaType             string             `json:"mediaType,omitempty"`
	BookmarkPosition      jsontime.UnixMilli `json:"bookmarkPosition,omitempty"`   // Added in 1.10.1
	OriginalWidth         int                `json:"originalWidth,omitempty"`      // Added in 1.13.0
	OriginalHeight        int                `json:"originalHeight,omitempty"`     // Added in 1.13.0
	Played                jsontime.UnixMilli `json:"played,omitempty"`             // OpenSubsonic addition
	BPM                   int                `json:"bpm,omitempty"`                // OpenSubsonic addition
	Comment               string             `json:"comment,omitempty"`            // OpenSubsonic addition
	SortName              string             `json:"sortName,omitempty"`           // OpenSubsonic addition
	MusicBrainzID         string             `json:"musicBrainzId,omitempty"`      // OpenSubsonic addition
	Genres                []ItemGenre        `json:"genres,omitempty"`             // OpenSubsonic addition
	Artists               []ArtistID3        `json:"artists,omitempty"`            // OpenSubsonic addition
	DisplayArtist         string             `json:"displayArtist,omitempty"`      // OpenSubsonic addition
	AlbumArtists          []ArtistID3        `json:"albumArtists,omitempty"`       // OpenSubsonic addition
	DisplayAlbumArtist    string             `json:"displayAlbumArtist,omitempty"` // OpenSubsonic addition
	Contributors          []Contributor      `json:"contributors,omitempty"`       // OpenSubsonic addition
	DisplayComposer       string             `json:"displayComposer,omitempty"`    // OpenSubsonic addition
	Moods                 []string           `json:"moods,omitempty"`              // OpenSubsonic addition
	ReplayGain            *ReplayGain        `json:"replayGain,omitempty"`         // OpenSubsonic addition
}

// MediaType is the type of a media.
//
// Subsonic 1.16.1 Definition:
//
//	<xs:simpleType name="MediaType">
//	    <xs:restriction base="xs:string">
//	        <xs:enumeration value="music"/>
//	        <xs:enumeration value="podcast"/>
//	        <xs:enumeration value="audiobook"/>
//	        <xs:enumeration value="video"/>
//	    </xs:restriction>
//	</xs:simpleType>
type MediaType string

const (
	MediaTypeMusic     MediaType = "music"
	MediaTypePodcast   MediaType = "podcast"
	MediaTypeAudioBook MediaType = "audiobook"
	MediaTypeVideo     MediaType = "video"
)

// NowPlaying is a list of currently playing songs.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="NowPlaying">
//	    <xs:sequence>
//	        <xs:element name="entry" type="sub:NowPlayingEntry" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/nowplaying/
type NowPlaying struct {
	Entry []NowPlayingEntry `json:"entry,omitempty"`
}

// NowPlayingEntry is a currently playing song.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="NowPlayingEntry">
//	    <xs:complexContent>
//	        <xs:extension base="sub:Child">
//	            <xs:attribute name="username" type="xs:string" use="required"/>
//	            <xs:attribute name="minutesAgo" type="xs:int" use="required"/>
//	            <xs:attribute name="playerId" type="xs:int" use="required"/>
//	            <xs:attribute name="playerName" type="xs:string" use="optional"/>
//	        </xs:extension>
//	    </xs:complexContent>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/nowplayingentry/
type NowPlayingEntry struct {
	Child
	Username   string `json:"username"`
	MinutesAgo int    `json:"minutesAgo"`
	PlayerID   string `json:"playerId"`
	PlayerName string `json:"playerName,omitempty"`
}

// SearchResult is a search result.
//
// Deprecated: Use [SearchResult2] or [SearchResult3].
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="SearchResult">
//	    <xs:sequence>
//	        <xs:element name="match" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	    <xs:attribute name="offset" type="xs:int" use="required"/>
//	    <xs:attribute name="totalHits" type="xs:int" use="required"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/searchresult/
type SearchResult struct {
	Match     []Child `json:"match,omitempty"`
	Offset    int     `json:"offset"`
	TotalHits int     `json:"totalHits"`
}

// SearchResult2 is a search result.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="SearchResult2">
//	    <xs:sequence>
//	        <xs:element name="artist" type="sub:Artist" minOccurs="0" maxOccurs="unbounded"/>
//	        <xs:element name="album" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	        <xs:element name="song" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/searchresult2/
type SearchResult2 struct {
	Artist []Artist `json:"artist,omitempty"`
	Album  []Child  `json:"album,omitempty"`
	Song   []Child  `json:"song,omitempty"`
}

// SearchResult3 is an ID3 search result.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="SearchResult3">
//	    <xs:sequence>
//	        <xs:element name="artist" type="sub:ArtistID3" minOccurs="0" maxOccurs="unbounded"/>
//	        <xs:element name="album" type="sub:AlbumID3" minOccurs="0" maxOccurs="unbounded"/>
//	        <xs:element name="song" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/searchresult3/
type SearchResult3 struct {
	Artist []ArtistID3 `json:"artist,omitempty"`
	Album  []AlbumID3  `json:"album,omitempty"`
	Song   []Child     `json:"song,omitempty"`
}

// Playlists is a list of playlists.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Playlists">
//	    <xs:sequence>
//	        <xs:element name="playlist" type="sub:Playlist" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/playlists/
type Playlists struct {
	Playlist []Playlist `json:"playlist,omitempty"`
}

// Playlist is a playlist.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Playlist">
//	    <xs:sequence>
//	        <xs:element name="allowedUser" type="xs:string" minOccurs="0" maxOccurs="unbounded"/> <!--Added in 1.8.0-->
//	    </xs:sequence>
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	    <xs:attribute name="name" type="xs:string" use="required"/>
//	    <xs:attribute name="comment" type="xs:string" use="optional"/>   <!--Added in 1.8.0-->
//	    <xs:attribute name="owner" type="xs:string" use="optional"/>     <!--Added in 1.8.0-->
//	    <xs:attribute name="public" type="xs:boolean" use="optional"/>   <!--Added in 1.8.0-->
//	    <xs:attribute name="songCount" type="xs:int" use="required"/>    <!--Added in 1.8.0-->
//	    <xs:attribute name="duration" type="xs:int" use="required"/>     <!--Added in 1.8.0-->
//	    <xs:attribute name="created" type="xs:dateTime" use="required"/> <!--Added in 1.8.0-->
//	    <xs:attribute name="changed" type="xs:dateTime" use="required"/> <!--Added in 1.13.0-->
//	    <xs:attribute name="coverArt" type="xs:string" use="optional"/>  <!--Added in 1.11.0-->
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/playlist/
type Playlist struct {
	ID          SubsonicID       `json:"id"`
	Name        string           `json:"name"`
	SongCount   int              `json:"songCount"`             // Added in 1.8.0
	Duration    SubsonicDuration `json:"duration"`              // Added in 1.8.0
	Created     time.Time        `json:"created"`               // Added in 1.8.0
	Changed     time.Time        `json:"changed"`               // Added in 1.13.0
	Comment     string           `json:"comment,omitempty"`     // Added in 1.8.0
	Owner       string           `json:"owner,omitempty"`       // Added in 1.8.0
	Public      bool             `json:"public,omitempty"`      // Added in 1.8.0
	CoverArt    string           `json:"coverArt,omitempty"`    // Added in 1.11.0
	AllowedUser []string         `json:"allowedUser,omitempty"` // Added in 1.8.0
}

// PlaylistWithSongs is a playlist with songs.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="PlaylistWithSongs">
//	    <xs:complexContent>
//	        <xs:extension base="sub:Playlist">
//	            <xs:sequence>
//	                <xs:element name="entry" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	            </xs:sequence>
//	        </xs:extension>
//	    </xs:complexContent>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/playlistwithsongs/
type PlaylistWithSongs struct {
	Playlist
	Entry []Child `json:"entry,omitempty"`
}

// JukeboxStatus is the status of the jukebox.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="JukeboxStatus">
//	    <xs:attribute name="currentIndex" type="xs:int" use="required"/>
//	    <xs:attribute name="playing" type="xs:boolean" use="required"/>
//	    <xs:attribute name="gain" type="xs:float" use="required"/>
//	    <xs:attribute name="position" type="xs:int" use="optional"/> <!--Added in 1.7.0-->
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/jukeboxstatus/
type JukeboxStatus struct {
	CurrentIndex int     `json:"currentIndex"`
	Playing      bool    `json:"playing"`
	Gain         float32 `json:"gain"`
	Position     *int    `json:"position,omitempty"` // Added in 1.7.0
}

// JukeboxPlaylist is a jukebox playlist.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="JukeboxPlaylist">
//	    <xs:complexContent>
//	        <xs:extension base="sub:JukeboxStatus">
//	            <xs:sequence>
//	                <xs:element name="entry" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	            </xs:sequence>
//	        </xs:extension>
//	    </xs:complexContent>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/jukeboxplaylist/
type JukeboxPlaylist struct {
	JukeboxStatus
	Entry []Child `json:"entry,omitempty"`
}

// ChatMessages is a list of chat messages.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="ChatMessages">
//	    <xs:sequence>
//	        <xs:element name="chatMessage" type="sub:ChatMessage" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/chatmessages/
type ChatMessages struct {
	ChatMessage []ChatMessage `json:"chatMessage,omitempty"`
}

// ChatMessage is a chat message.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="ChatMessage">
//	    <xs:attribute name="username" type="xs:string" use="required"/>
//	    <xs:attribute name="time" type="xs:long" use="required"/>
//	    <xs:attribute name="message" type="xs:string" use="required"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/chatmessage/
type ChatMessage struct {
	Username string             `json:"username"`
	Time     jsontime.UnixMilli `json:"time"`
	Message  string             `json:"message"`
}

// AlbumList is a list of albums.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="AlbumList">
//	    <xs:sequence>
//	        <xs:element name="album" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/albumlist/
type AlbumList struct {
	Album []Child `json:"album,omitempty"`
}

// AlbumList2 is a list of ID3 albums.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="AlbumList2">
//	    <xs:sequence>
//	        <xs:element name="album" type="sub:AlbumID3" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/albumlist2/
type AlbumList2 struct {
	Album []AlbumID3 `json:"album,omitempty"`
}

// Songs is a list of songs
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Songs">
//	    <xs:sequence>
//	        <xs:element name="song" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
type Songs struct {
	Song []Child `json:"song"`
}

// Lyrics is the lyrics for a song.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Lyrics" mixed="true">
//	    <xs:attribute name="artist" type="xs:string" use="optional"/>
//	    <xs:attribute name="title" type="xs:string" use="optional"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/lyrics/
type Lyrics struct {
	Value  string `json:"value"`            // The lyrics for the song.
	Artist string `json:"artist,omitempty"` // The artist name.
	Title  string `json:"title,omitempty"`  // The song title.
}

// Podcasts is a list of podcasts.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Podcasts">
//	    <xs:sequence>
//	        <xs:element name="channel" type="sub:PodcastChannel" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/podcasts/
type Podcasts struct {
	Channel []PodcastChannel `json:"channel"`
}

// PodcastChannel is a podcast channel (the metadata about a podcast).
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="PodcastChannel">
//	    <xs:sequence>
//	        <xs:element name="episode" type="sub:PodcastEpisode" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	    <xs:attribute name="url" type="xs:string" use="required"/>
//	    <xs:attribute name="title" type="xs:string" use="optional"/>
//	    <xs:attribute name="description" type="xs:string" use="optional"/>
//	    <xs:attribute name="coverArt" type="xs:string" use="optional"/> <!-- Added in 1.13.0 -->
//	    <xs:attribute name="originalImageUrl" type="xs:string" use="optional"/> <!-- Added in 1.13.0 -->
//	    <xs:attribute name="status" type="sub:PodcastStatus" use="required"/>
//	    <xs:attribute name="errorMessage" type="xs:string" use="optional"/>
//	</xs:complexType>
type PodcastChannel struct {
	Episode          []PodcastEpisode `json:"episode"`
	ID               SubsonicID       `json:"id"`
	URL              string           `json:"url"`
	Title            string           `json:"title,omitempty"`
	Description      string           `json:"description,omitempty"`
	CoverArt         string           `json:"coverArt,omitempty"` // Added in 1.13.0
	OriginalImageURL string           `json:"originalImageUrl,omitempty"`
	Status           PodcastStatus    `json:"status"`
	ErrorMessage     string           `json:"errorMessage,omitempty"`
}

// NewestPodcasts is a list of newest podcasts.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="NewestPodcasts">
//	    <xs:sequence>
//	        <xs:element name="episode" type="sub:PodcastEpisode" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/newestpodcasts/
type NewestPodcasts struct {
	Episode []PodcastEpisode `json:"episode"`
}

// PodcastEpisode is a podcast episode.
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="PodcastEpisode">
//	    <xs:complexContent>
//	        <xs:extension base="sub:Child">
//	            <xs:attribute name="streamId" type="xs:string" use="optional"/> <!-- Use this ID for streaming the podcast. -->
//	            <xs:attribute name="channelId" type="xs:string" use="required"/> <!-- Added in 1.13.0 -->
//	            <xs:attribute name="description" type="xs:string" use="optional"/>
//	            <xs:attribute name="status" type="sub:PodcastStatus" use="required"/>
//	            <xs:attribute name="publishDate" type="xs:dateTime" use="optional"/>
//	        </xs:extension>
//	    </xs:complexContent>
//	</xs:complexType>
type PodcastEpisode struct {
	Child
	StreamID    string        `json:"streamId,omitempty"`
	ChannelID   string        `json:"channelId"` // Added in 1.13.0
	Description string        `json:"description,omitempty"`
	Status      PodcastStatus `json:"status"`
	PublishDate *time.Time    `json:"publishDate,omitempty"`
}

// PodcastStatus is the status of a podcast.
//
// Subsonic 1.16.1 Definition:
//
//	<xs:simpleType name="PodcastStatus">
//	    <xs:restriction base="xs:string">
//	        <xs:enumeration value="new"/>
//	        <xs:enumeration value="downloading"/>
//	        <xs:enumeration value="completed"/>
//	        <xs:enumeration value="error"/>
//	        <xs:enumeration value="deleted"/>
//	        <xs:enumeration value="skipped"/>
//	    </xs:restriction>
//	</xs:simpleType>
type PodcastStatus string

const (
	PodcastStatusNew         PodcastStatus = "new"
	PodcastStatusDownloading PodcastStatus = "downloading"
	PodcastStatusCompleted   PodcastStatus = "completed"
	PodcastStatusError       PodcastStatus = "error"
	PodcastStatusDeleted     PodcastStatus = "deleted"
	PodcastStatusSkipped     PodcastStatus = "skipped"
)

// InternetRadioStations is a list of internet radio stations.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="InternetRadioStations">
//	    <xs:sequence>
//	        <xs:element name="internetRadioStation" type="sub:InternetRadioStation" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/internetradiostations/
type InternetRadioStations struct {
	InternetRadioStation []InternetRadioStation `json:"internetRadioStation,omitempty"`
}

// InternetRadioStation is an internet radio station.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="InternetRadioStation">
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	    <xs:attribute name="name" type="xs:string" use="required"/>
//	    <xs:attribute name="streamUrl" type="xs:string" use="required"/>
//	    <xs:attribute name="homePageUrl" type="xs:string" use="optional"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/internetradiostation/
type InternetRadioStation struct {
	ID          SubsonicID `json:"id"`
	Name        string     `json:"name"`
	StreamURL   string     `json:"streamUrl"`
	HomePageURL string     `json:"homePageUrl,omitempty"`
}

// Bookmarks is a list of bookmarks.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Bookmarks">
//	    <xs:sequence>
//	        <xs:element name="bookmark" type="sub:Bookmark" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/bookmarks/
type Bookmarks struct {
	Bookmark []Bookmark `json:"bookmark,omitempty"`
}

// Bookmark is a bookmark.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Bookmark">
//	    <xs:sequence>
//	        <xs:element name="entry" type="sub:Child" minOccurs="1" maxOccurs="1"/>
//	    </xs:sequence>
//	    <xs:attribute name="position" type="xs:long" use="required"/> <!-- In milliseconds -->
//	    <xs:attribute name="username" type="xs:string" use="required"/>
//	    <xs:attribute name="comment" type="xs:string" use="optional"/>
//	    <xs:attribute name="created" type="xs:dateTime" use="required"/>
//	    <xs:attribute name="changed" type="xs:dateTime" use="required"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/bookmark/
type Bookmark struct {
	Position int64     `json:"position"`
	Username string    `json:"username"`
	Comment  string    `json:"comment,omitempty"`
	Created  time.Time `json:"created"`
	Changed  time.Time `json:"changed"`
	Entry    Child     `json:"entry"` // TODO not entirely sure what shape this is (it might be a list)
}

// PlayQueue is a play queue.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="PlayQueue">
//	    <xs:sequence>
//	        <xs:element name="entry" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	    <xs:attribute name="current" type="xs:int" use="optional"/>   <!-- ID of currently playing track -->
//	    <xs:attribute name="position" type="xs:long" use="optional"/> <!-- Position in milliseconds of currently playing track -->
//	    <xs:attribute name="username" type="xs:string" use="required"/>
//	    <xs:attribute name="changed" type="xs:dateTime" use="required"/>
//	    <xs:attribute name="changedBy" type="xs:string" use="required"/> <!-- Name of client app -->
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/playqueue/
type PlayQueue struct {
	Entry     []Child    `json:"entry"`
	Current   SubsonicID `json:"current,omitempty"`
	Position  int64      `json:"position,omitempty"`
	Username  string     `json:"username"`
	Changed   time.Time  `json:"changed"`
	ChangedBy string     `json:"changedBy"` // Name of client app
}

// Shares is a list of shared media.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Shares">
//	    <xs:sequence>
//	        <xs:element name="share" type="sub:Share" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/shares/
type Shares struct {
	Share []Share `json:"share,omitempty"`
}

// Share is a shared media.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Share">
//	    <xs:sequence>
//	        <xs:element name="entry" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	    <xs:attribute name="id" type="xs:string" use="required"/>
//	    <xs:attribute name="url" type="xs:string" use="required"/>
//	    <xs:attribute name="description" type="xs:string" use="optional"/>
//	    <xs:attribute name="username" type="xs:string" use="required"/>
//	    <xs:attribute name="created" type="xs:dateTime" use="required"/>
//	    <xs:attribute name="expires" type="xs:dateTime" use="optional"/>
//	    <xs:attribute name="lastVisited" type="xs:dateTime" use="optional"/>
//	    <xs:attribute name="visitCount" type="xs:int" use="required"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/share/
type Share struct {
	ID          SubsonicID `json:"id"`
	URL         string     `json:"url"`
	Description string     `json:"description,omitempty"`
	Username    string     `json:"username"`
	Created     time.Time  `json:"created"`
	Expires     *time.Time `json:"expires,omitempty"`
	LastVisited *time.Time `json:"lastVisited,omitempty"`
	VisitCount  int        `json:"visitCount"`
	Entry       Child      `json:"entry"` // TODO not entirely sure what shape this is (it might be a list)
}

// Starred is a list of songs by genre.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Starred">
//	    <xs:sequence>
//	        <xs:element name="artist" type="sub:Artist" minOccurs="0" maxOccurs="unbounded"/>
//	        <xs:element name="album" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	        <xs:element name="song" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/starred/
type Starred struct {
	Artist []Artist `json:"artist"`
	Album  []Child  `json:"album"`
	Song   []Child  `json:"song"`
}

// AlbumInfo is the information about an album.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="AlbumInfo">
//	    <xs:sequence>
//	        <xs:element name="notes" type="xs:string" minOccurs="0" maxOccurs="1"/>
//	        <xs:element name="musicBrainzId" type="xs:string" minOccurs="0" maxOccurs="1"/>
//	        <xs:element name="lastFmUrl" type="xs:string" minOccurs="0" maxOccurs="1"/>
//	        <xs:element name="smallImageUrl" type="xs:string" minOccurs="0" maxOccurs="1"/>
//	        <xs:element name="mediumImageUrl" type="xs:string" minOccurs="0" maxOccurs="1"/>
//	        <xs:element name="largeImageUrl" type="xs:string" minOccurs="0" maxOccurs="1"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/albuminfo/
type AlbumInfo struct {
	Notes          []string `json:"notes"`
	MusicBrainzID  []string `json:"musicBrainzId"`
	LastFMURL      []string `json:"lastFmUrl"`
	SmallImageURL  []string `json:"smallImageUrl"`
	MediumImageURL []string `json:"mediumImageUrl"`
	LargeImageURL  []string `json:"largeImageUrl"`
}

// ArtistInfoBase is the base artist info struct that is used by both
// [ArtistInfo] and [ArtistInfo2].
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="ArtistInfoBase">
//	    <xs:sequence>
//	        <xs:element name="biography" type="xs:string" minOccurs="0" maxOccurs="1"/>
//	        <xs:element name="musicBrainzId" type="xs:string" minOccurs="0" maxOccurs="1"/>
//	        <xs:element name="lastFmUrl" type="xs:string" minOccurs="0" maxOccurs="1"/>
//	        <xs:element name="smallImageUrl" type="xs:string" minOccurs="0" maxOccurs="1"/>
//	        <xs:element name="mediumImageUrl" type="xs:string" minOccurs="0" maxOccurs="1"/>
//	        <xs:element name="largeImageUrl" type="xs:string" minOccurs="0" maxOccurs="1"/>
//	    </xs:sequence>
//	</xs:complexType>
type ArtistInfoBase struct {
	Biography      []string `json:"biography"`
	MusicBrainzID  []string `json:"musicBrainzId"`
	LastFMURL      []string `json:"lastFmUrl"`
	SmallImageURL  []string `json:"smallImageUrl"`
	MediumImageURL []string `json:"mediumImageUrl"`
	LargeImageURL  []string `json:"largeImageUrl"`
}

// ArtistInfo is the information about an artist.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="ArtistInfo">
//	    <xs:complexContent>
//	        <xs:extension base="sub:ArtistInfoBase">
//	            <xs:sequence>
//	                <xs:element name="similarArtist" type="sub:Artist" minOccurs="0" maxOccurs="unbounded"/>
//	            </xs:sequence>
//	        </xs:extension>
//	    </xs:complexContent>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/artistinfo/
type ArtistInfo struct {
	ArtistInfoBase
	SimilarArtist []Artist `json:"similarArtist,omitempty"`
}

// ArtistInfo2 is the information about an ID3 artist.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="ArtistInfo2">
//	    <xs:complexContent>
//	        <xs:extension base="sub:ArtistInfoBase">
//	            <xs:sequence>
//	                <xs:element name="similarArtist" type="sub:ArtistID3" minOccurs="0" maxOccurs="unbounded"/>
//	            </xs:sequence>
//	        </xs:extension>
//	    </xs:complexContent>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/artistinfo2/
type ArtistInfo2 struct {
	ArtistInfoBase
	SimilarArtist []ArtistID3 `json:"similarArtist,omitempty"`
}

// SimilarSongs is a list of similar songs.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="SimilarSongs">
//	    <xs:sequence>
//	        <xs:element name="song" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/similarsongs/
type SimilarSongs struct {
	Song []Child `json:"song,omitempty"`
}

// SimilarSongs is a list of similar songs, organized by ID3 tags.
//
// This is the same as [SimilarSongs], but with the songs organized by ID3.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="SimilarSongs2">
//	    <xs:sequence>
//	        <xs:element name="song" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/similarsongs2/
type SimilarSongs2 struct {
	Song []Child `json:"song,omitempty"`
}

// TopSongs is a list of top songs.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="TopSongs">
//	    <xs:sequence>
//	        <xs:element name="song" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/topsongs/
type TopSongs struct {
	Song []Child `json:"song,omitempty"`
}

// Starred2 is a list of songs by genre.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Starred2">
//	    <xs:sequence>
//	        <xs:element name="artist" type="sub:ArtistID3" minOccurs="0" maxOccurs="unbounded"/>
//	        <xs:element name="album" type="sub:AlbumID3" minOccurs="0" maxOccurs="unbounded"/>
//	        <xs:element name="song" type="sub:Child" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/starred2/
type Starred2 struct {
	Artist []ArtistID3 `json:"artist"`
	Album  []AlbumID3  `json:"album"`
	Song   []Child     `json:"song"`
}

// License is the software license.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="License">
//	    <xs:attribute name="valid" type="xs:boolean" use="required"/>
//	    <xs:attribute name="email" type="xs:string" use="optional"/>
//	    <xs:attribute name="licenseExpires" type="xs:dateTime" use="optional"/>
//	    <xs:attribute name="trialExpires" type="xs:dateTime" use="optional"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/license/
type License struct {
	Valid          bool      `json:"valid"`
	Email          string    `json:"email,omitempty"`
	LicenseExpires time.Time `json:"licenseExpires,omitempty"`
	TrialExpires   time.Time `json:"trialExpires,omitempty"`
}

// ScanStatus is the status of the media scanner.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="ScanStatus">
//	    <xs:attribute name="scanning" type="xs:boolean" use="required"/>
//	    <xs:attribute name="count" type="xs:long" use="optional"/>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/scanstatus/
type ScanStatus struct {
	Scanning bool  `json:"scanning"`        // Whether the scanner is currently running
	Count    int64 `json:"count,omitempty"` // The number of files scanned so far
}

// Users is a list of Subsonic users.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Users">
//	    <xs:sequence>
//	        <xs:element name="user" type="sub:User" minOccurs="0" maxOccurs="unbounded"/>
//	    </xs:sequence>
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/users/
type Users struct {
	User []User `json:"user"`
}

// User is a Subsonic user.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="User">
//	    <xs:sequence>
//	        <xs:element name="folder" type="xs:int" minOccurs="0" maxOccurs="unbounded"/> <!-- Added in 1.12.0 -->
//	    </xs:sequence>
//	    <xs:attribute name="username" type="xs:string" use="required"/>
//	    <xs:attribute name="email" type="xs:string" use="optional"/> <!-- Added in 1.6.0 -->
//	    <xs:attribute name="scrobblingEnabled" type="xs:boolean" use="required"/> <!-- Added in 1.7.0 -->
//	    <xs:attribute name="maxBitRate" type="xs:int" use="optional"/> <!-- In Kbps, added in 1.13.0 -->
//	    <xs:attribute name="adminRole" type="xs:boolean" use="required"/>
//	    <xs:attribute name="settingsRole" type="xs:boolean" use="required"/>
//	    <xs:attribute name="downloadRole" type="xs:boolean" use="required"/>
//	    <xs:attribute name="uploadRole" type="xs:boolean" use="required"/>
//	    <xs:attribute name="playlistRole" type="xs:boolean" use="required"/>
//	    <xs:attribute name="coverArtRole" type="xs:boolean" use="required"/>
//	    <xs:attribute name="commentRole" type="xs:boolean" use="required"/>
//	    <xs:attribute name="podcastRole" type="xs:boolean" use="required"/>
//	    <xs:attribute name="streamRole" type="xs:boolean" use="required"/>
//	    <xs:attribute name="jukeboxRole" type="xs:boolean" use="required"/>
//	    <xs:attribute name="shareRole" type="xs:boolean" use="required"/> <!-- Added in 1.7.0 -->
//	    <xs:attribute name="videoConversionRole" type="xs:boolean" use="required"/> <!-- Added in 1.14.0 -->
//	    <xs:attribute name="avatarLastChanged" type="xs:dateTime" use="optional"/> <!-- Added in 1.14.0 -->
//	</xs:complexType>
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/user/
type User struct {
	Folder              []int     `json:"folder,omitempty"` // Added in 1.12.0y"`
	Username            string    `json:"username"`
	Email               string    `json:"email,omitempty"`      // Added in 1.6.0
	ScrobblingEnabled   bool      `json:"scrobblingEnabled"`    // Added in 1.7.0
	MaxBitRate          int       `json:"maxBitRate,omitempty"` // In Kbps, added in 1.13.0
	AdminRole           bool      `json:"adminRole"`
	SettingsRole        bool      `json:"settingsRole"`
	DownloadRole        bool      `json:"downloadRole"`
	UploadRole          bool      `json:"uploadRole"`
	PlaylistRole        bool      `json:"playlistRole"`
	CoverArtRole        bool      `json:"coverArtRole"`
	CommentRole         bool      `json:"commentRole"`
	PodcastRole         bool      `json:"podcastRole"`
	SteramRole          bool      `json:"streamRole"`
	JukeboxRole         bool      `json:"jukeboxRole"`
	ShareRole           bool      `json:"shareRole"`                   // Added in 1.7.0
	VideoConversionRole bool      `json:"videoConversionRole"`         // Added in 1.14.0
	AvatarLastChanged   time.Time `json:"avatarLastChanged,omitempty"` // Added in 1.14.0
}

// Contributor is a contributing artist for a song or album.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/contributor/
type Contributor struct {
	Role    string    `json:"role"`
	SubRole string    `json:"subRole"`
	Artist  ArtistID3 `json:"artist"`
}

// DiscTitle is a disc title for an album.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/disctitle/
type DiscTitle struct {
	Disc  int    `json:"disc"`
	Title string `json:"title"`
}

// ItemDate is a date for a media item that may be just a year, or year-month,
// or full date.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/itemdate/
type ItemDate struct {
	Year  int
	Month time.Month
	Day   int
}

// ItemGenre is a genre returned in list of genres for an item.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/itemgenre/
type ItemGenre struct {
	Name string `json:"name"`
}

// Line is one line of a song lyric.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/line/
type Line struct {
	Value string `json:"value"`
	Start int64  `json:"start,omitempty"`
}

// LyricsList is a list of structured lyrics for a song.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/lyricslist/
type LyricsList struct {
	StructuredLyrics []StructuredLyrics `json:"structuredLyrics,omitempty"`
}

// OpenSubsonicExtension is a supported OpenSubsonic API extension.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/opensubsonicextension/
type OpenSubsonicExtension struct {
	Name     string `json:"name"`
	Versions []int  `json:"versions"`
}

// RecordLabel is a record label for an album.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/recordlabel/
type RecordLabel struct {
	// The record label name.
	Name string `json:"name"`
}

// ReplayGain is the replay gain data of a song.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/replaygain/
type ReplayGain struct {
	// TrackGain is the track replay gain value in dB.
	TrackGain float64 `json:"trackGain"`
	// AlbumGain is the album replay gain value in dB.
	AlbumGain float64 `json:"albumGain"`
	// The track peak value.
	TrackPeak float64 `json:"trackPeak"`
	// The album peak value.
	AlbumPeak float64 `json:"albumPeak"`
	// The base gain value in dB.
	BaseGain float64 `json:"baseGain"`
	// An optional fallback gain that clients should apply when the
	// corresponding gain value is missing.
	FallbackGain float64 `json:"fallbackGain"`
}

// StructuredLyrics is the structured lyrics for a song.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/structuredlyrics/
type StructuredLyrics struct {
	Lang          string `json:"lang"`
	Synced        bool   `json:"synced"`
	Line          []Line `json:"line"`
	DisplayArtist string `json:"displayArtist"`
	DisplayTitle  string `json:"displayTitle"`
	Offset        int64  `json:"offset"`
}
