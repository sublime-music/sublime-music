package subsonic

import (
	"time"

	"go.mau.fi/util/jsontime"
)

// AlbumID3 is an album from ID3 tags.
//
// Docs: [OpenSubsonic]
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
	PlayCount           int64         `json:"playCount,omitempty"`
	Created             time.Time     `json:"created,omitempty"`
	Starred             *time.Time    `json:"starred,omitempty"`
	Year                int           `json:"year,omitempty"`
	Genre               string        `json:"genre,omitempty"`
	Played              *time.Time    `json:"played,omitempty"`
	UserRating          int           `json:"userRating,omitempty"`
	RecordLabels        []RecordLabel `json:"recordLabels,omitempty"`
	MusicBrainzID       string        `json:"musicBrainzId,omitempty"`
	Genres              []ItemGenre   `json:"genres,omitempty"`
	Artists             []ArtistID3   `json:"artists,omitempty"`
	DisplayArtist       string        `json:"displayArtist,omitempty"`
	ReleaseTypes        []string      `json:"releaseTypes,omitempty"`
	Moods               []string      `json:"moods,omitempty"`
	SortName            string        `json:"sortName,omitempty"`
	OriginalReleaseDate ItemDate      `json:"originalReleaseDate,omitempty"`
	IsCompilation       bool          `json:"isCompilation,omitempty"`
	DiscTitles          []DiscTitle   `json:"discTitles,omitempty"`
}

// AlbumID3WithSongs is an album with songs.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/albumid3withsongs/
type AlbumID3WithSongs struct {
	AlbumID3
	Song []Song `json:"song,omitempty"`
}

// AlbumInfo is the information about an album.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/albuminfo/
type AlbumInfo struct {
	Notes          string `json:"notes"`
	MusicBrainzID  string `json:"musicBrainzId"`
	SmallImageURL  string `json:"smallImageUrl"`
	MediumImageURL string `json:"mediumImageUrl"`
	LargeImageURL  string `json:"largeImageUrl"`
}

// AlbumList is a list of albums.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/albumlist/
type AlbumList struct {
	Album []Child `json:"album,omitempty"`
}

// AlbumList2 is a list of ID3 albums.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/albumlist2/
type AlbumList2 struct {
	Album []AlbumID3 `json:"album,omitempty"`
}

// Artist is an artist.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/artist/
type Artist struct {
	ID             SubsonicID          `json:"id"`
	Name           string              `json:"name"`
	ArtistImageURL string              `json:"artistImageUrl,omitempty"`
	Starred        *time.Time          `json:"starred,omitempty"`
	UserRating     int                 `json:"userRating,omitempty"`
	AverageRating  float64             `json:"averageRating,omitempty"`
	Album          []AlbumID3WithSongs `json:"album,omitempty"`
}

// ArtistID3 is an artist from ID3 tags.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/artistid3/
type ArtistID3 struct {
	ID             SubsonicID `json:"id"`
	Name           string     `json:"name"`
	CoverArt       string     `json:"coverArt,omitempty"`
	ArtistImageURL string     `json:"artistImageUrl,omitempty"`
	AlbumCount     int        `json:"albumCount,omitempty"`
	Starred        bool       `json:"starred,omitempty"`
	MusicBrainzID  string     `json:"musicBrainzId,omitempty"`
	SortName       string     `json:"sortName,omitempty"`
	Roles          []string   `json:"roles,omitempty"`
}

// ArtistInfo is the information about an artist.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/artistinfo/
type ArtistInfo struct {
	Biography      string   `json:"biography"`
	MusicBrainzID  string   `json:"musicBrainzId"`
	LastFMURL      string   `json:"lastFmUrl"`
	SmallImageURL  string   `json:"smallImageUrl"`
	MediumImageURL string   `json:"mediumImageUrl"`
	LargeImageURL  string   `json:"largeImageUrl"`
	SimilarArtist  []Artist `json:"similarArtist,omitempty"`
}

// ArtistInfo2 is the information about an ID3 artist.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/artistinfo2/
type ArtistInfo2 struct {
	Biography      string      `json:"biography"`
	MusicBrainzID  string      `json:"musicBrainzId"`
	LastFMURL      string      `json:"lastFmUrl"`
	SmallImageURL  string      `json:"smallImageUrl"`
	MediumImageURL string      `json:"mediumImageUrl"`
	LargeImageURL  string      `json:"largeImageUrl"`
	SimilarArtist  []ArtistID3 `json:"similarArtist,omitempty"`
}

// Artists is a list of ID3 artists.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/artistsid3/
type Artists struct {
	IgnoredArticles IgnoredArticles `json:"ignoredArticles,omitempty"`
	Index           []IndexID3      `json:"index,omitempty"`
}

// Bookmark is a bookmark.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/bookmark/
type Bookmark struct {
	Position int64     `json:"position"`
	Username string    `json:"username"`
	Comment  string    `json:"comment"`
	Created  time.Time `json:"created"`
	Changed  time.Time `json:"changed"`
	Entry    Child     `json:"entry"`
}

// Bookmarks is a list of bookmarks.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/bookmarks/
type Bookmarks struct {
	Bookmark []Bookmark `json:"bookmark,omitempty"`
}

// ChatMessage is a chat message.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/chatmessage/
type ChatMessage struct {
	Username string             `json:"username"`
	Time     jsontime.UnixMilli `json:"time"`
	Message  string             `json:"message"`
}

// ChatMessages is a list of chat messages.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/chatmessages/
type ChatMessages struct {
	ChatMessage []ChatMessage `json:"chatMessage,omitempty"`
}

// Child is a media.
type Child struct {
	ID                    SubsonicID    `json:"id"`
	Parent                SubsonicID    `json:"parent,omitempty"`
	IsDir                 bool          `json:"isDir"`
	Title                 string        `json:"title"`
	Album                 string        `json:"album,omitempty"`
	Artist                string        `json:"artist,omitempty"`
	Track                 int           `json:"track,omitempty"`
	Year                  int           `json:"year,omitempty"`
	Genre                 string        `json:"genre,omitempty"`
	CoverArt              string        `json:"coverArt,omitempty"`
	Size                  int64         `json:"size,omitempty"`
	ContentType           string        `json:"contentType,omitempty"`
	Suffix                string        `json:"suffix,omitempty"`
	TranscodedContentType string        `json:"transcodedContentType,omitempty"`
	TranscodedSuffix      string        `json:"transcodedSuffix,omitempty"`
	Duration              int           `json:"duration,omitempty"`
	BitRate               int           `json:"bitRate,omitempty"`
	Path                  string        `json:"path,omitempty"`
	IsVideo               bool          `json:"isVideo,omitempty"`
	UserRating            int           `json:"userRating,omitempty"`
	AverageRating         float64       `json:"averageRating,omitempty"`
	PlayCount             int64         `json:"playCount,omitempty"`
	DiscNumber            int           `json:"discNumber,omitempty"`
	Created               *time.Time    `json:"created,omitempty"`
	Starred               *time.Time    `json:"starred,omitempty"`
	AlbumID               SubsonicID    `json:"albumId,omitempty"`
	ArtistID              SubsonicID    `json:"artistId,omitempty"`
	Type                  string        `json:"type,omitempty"`
	MediaType             string        `json:"mediaType,omitempty"`
	BookmarkPosition      int64         `json:"bookmarkPosition,omitempty"`
	OriginalWidth         int           `json:"originalWidth,omitempty"`
	OriginalHeight        int           `json:"originalHeight,omitempty"`
	Played                *time.Time    `json:"played,omitempty"`
	BPM                   int           `json:"bpm,omitempty"`
	Comment               string        `json:"comment,omitempty"`
	SortName              string        `json:"sortName,omitempty"`
	MusicBrainzID         string        `json:"musicBrainzId,omitempty"`
	Genres                []ItemGenre   `json:"genres,omitempty"`
	Artists               []ArtistID3   `json:"artists,omitempty"`
	DisplayArtist         string        `json:"displayArtist,omitempty"`
	AlbumArtists          []ArtistID3   `json:"albumArtists,omitempty"`
	DisplayAlbumArtist    string        `json:"displayAlbumArtist,omitempty"`
	Contributors          []Contributor `json:"contributors,omitempty"`
	DisplayComposer       string        `json:"displayComposer,omitempty"`
	Moods                 []string      `json:"moods,omitempty"`
	ReplayGain            *ReplayGain   `json:"replayGain,omitempty"`
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

// Directory is a directory.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/directory/
type Directory struct {
	ID            SubsonicID `json:"id"`
	Name          string     `json:"name"`
	Parent        SubsonicID `json:"parent,omitempty"`
	Starred       bool       `json:"starred,omitempty"`
	UserRating    int        `json:"userRating,omitempty"`
	AverageRating float64    `json:"averageRating,omitempty"`
	PlayCount     int64      `json:"playCount,omitempty"`
	Child         []Child    `json:"child,omitempty"`
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

// Genre is a genre.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/genre/
type Genre struct {
	Value      string `json:"value"`
	Songcount  int    `json:"songCount"`
	Albumcount int    `json:"albumCount"`
}

// Genre is a list of genres.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/genres/
type Genres struct {
	Genre []Genre `json:"genre,omitempty"`
}

// Indexes is an indexed list of artists.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/indexes/
type Indexes struct {
	IgnoredArticles IgnoredArticles `json:"ignoredArticles,omitempty"`
	Index           []IndexID3      `json:"index,omitempty"`
}

// Indexes is an indexed list of ID3 artists.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/indexeid3/
type IndexID3 struct {
	Name   string      `json:"name"`
	Artist []ArtistID3 `json:"artist"`
}

// InternetRadioStation is an internet radio station.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/internetradiostation/
type InternetRadioStation struct {
	ID          SubsonicID `json:"id"`
	Name        string     `json:"name"`
	StreamURL   string     `json:"streamUrl"`
	HomepageURL string     `json:"homepageUrl"`
}

// InternetRadioStations is a list of internet radio stations.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/internetradiostations/
type InternetRadioStations struct {
	InternetRadioStation []InternetRadioStation `json:"internetRadioStation,omitempty"`
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

// JukeboxPlaylist is a jukebox playlist.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/jukeboxplaylist/
type JukeboxPlaylist struct {
	// TODO
}

// JukeboxStatus is the status of the jukebox.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/jukeboxstatus/
type JukeboxStatus struct {
	// TODO
}

// License is the software license.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/license/
type License struct {
	Valid          bool      `json:"valid"`
	Email          string    `json:"email"`
	LicenseExpires time.Time `json:"licenseExpires"`
	TrialExpires   time.Time `json:"trialExpires"`
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

// Lyrics is the lyrics for a song.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/lyrics/
type Lyrics struct {
	// The artist name.
	Artist string `json:"artist"`
	// The song title.
	Title string `json:"title"`
	// The lyrics for the song.
	Value string `json:"value"`
}

// LyricsList is a list of structured lyrics for a song.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/lyricslist/
type LyricsList struct {
	StructuredLyrics []StructuredLyrics `json:"structuredLyrics,omitempty"`
}

// MusicFolder is a music folder.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/musicfolder/
type MusicFolder struct {
	ID   SubsonicID `json:"id"`
	Name string     `json:"name,omitempty"`
}

// MusicFolders is a list of music folders.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/musicfolders/
type MusicFolders struct {
	MusicFolder []MusicFolder `json:"musicFolder,omitempty"`
}

// NewestPodcasts is a list of newest podcasts.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/newestpodcasts/
type NewestPodcasts struct {
	// TODO
}

// NowPlaying is a list of currently playing songs.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/nowplaying/
type NowPlaying struct {
	Entry []NowPlayingEntry `json:"entry,omitempty"`
}

// NowPlayingEntry is a currently playing song.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/nowplayingentry/
type NowPlayingEntry struct {
	Child
	Username   string `json:"username"`
	MinutesAgo int    `json:"minutesAgo"`
	PlayerID   string `json:"playerId"`
	PlayerName string `json:"playerName"`
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

// Playlist is a playlist.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/playlist/
type Playlist struct {
	ID          SubsonicID       `json:"id"`
	Name        string           `json:"name"`
	SongCount   int              `json:"songCount"`
	Duration    SubsonicDuration `json:"duration"`
	Created     time.Time        `json:"created"`
	Changed     time.Time        `json:"changed"`
	Comment     string           `json:"comment,omitempty"`
	Owner       string           `json:"owner,omitempty"`
	Public      bool             `json:"public,omitempty"`
	CoverArt    string           `json:"coverArt,omitempty"`
	AllowedUser []string         `json:"allowedUser,omitempty"`
}

// Playlists is a list of playlists.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/playlists/
type Playlists struct {
	Playlist []Playlist `json:"playlist,omitempty"`
}

// PlaylistWithSongs is a playlist with songs.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/playlistwithsongs/
type PlaylistWithSongs struct {
	Playlist
	Entry []Child `json:"entry,omitempty"`
}

// PlayQueue is a play queue.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/playqueue/
type PlayQueue struct {
	// TODO
}

// Podcasts is a list of podcasts.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/podcasts/
type Podcasts struct {
	// TODO
}

// RandomSongs is a list of random songs.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/randomsongs/
type RandomSongs struct {
	Song []Child `json:"song,omitempty"`
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

// ScanStatus is the status of the media scanner.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/scanstatus/
type ScanStatus struct {
	// Scanning indicates whether the scanner is currently running.
	Scanning bool `json:"scanning"`
	// Count is the number of files scanned so far.
	Count int `json:"count"`
}

// SearchResult is a search result.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/searchresult/
type SearchResult struct {
	// TODO
}

// SearchResult2 is a search result.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/searchresult2/
type SearchResult2 struct {
	// TODO
}

// SearchResult3 is a search result.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/searchresult3/
type SearchResult3 struct {
	Artist []ArtistID3 `json:"artist,omitempty"`
	Album  []AlbumID3  `json:"album,omitempty"`
	Song   []Child     `json:"song,omitempty"`
}

type Song struct {
	ID SubsonicID `json:"id"`
	// TODO
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

type Video struct {
	ID SubsonicID `json:"id"`
	// TODO
}

type Videos struct {
	Video []Video `json:"video,omitempty"`
}
