package subsonic

import (
	"context"
	"encoding/json"
	"net/url"
	"time"
)

type MusicFolder struct {
	ID   SubsonicID `json:"id"`
	Name string     `json:"name,omitempty"`
}

type MusicFolders struct {
	MusicFolder []MusicFolder `json:"musicFolder,omitempty"`
}

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

type IndexID3 struct {
	Name   string      `json:"name"`
	Artist []ArtistID3 `json:"artist"`
}

type Indexes struct {
	IgnoredArticles IgnoredArticles `json:"ignoredArticles,omitempty"`
	Index           []IndexID3      `json:"index,omitempty"`
}

type ItemGenre struct {
	Name string `json:"name"`
}

type Contributor struct {
	Role    string    `json:"role"`
	SubRole string    `json:"subRole"`
	Artist  ArtistID3 `json:"artist"`
}

type ReplayGain struct {
	TrackGain    float64 `json:"trackGain"`
	AlbumGain    float64 `json:"albumGain"`
	TrackPeak    float64 `json:"trackPeak"`
	AlbumPeak    float64 `json:"albumPeak"`
	BaseGain     float64 `json:"baseGain"`
	FallbackGain float64 `json:"fallbackGain"`
}

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

type Genre struct {
	Value      string `json:"value"`
	Songcount  int    `json:"songCount"`
	Albumcount int    `json:"albumCount"`
}

type Genres struct {
	Genre []Genre `json:"genre,omitempty"`
}

type Artists struct {
	IgnoredArticles IgnoredArticles `json:"ignoredArticles,omitempty"`
	Index           []IndexID3      `json:"index,omitempty"`
}

type RecordLabel struct {
	Name string `json:"name"`
}

type ItemDate time.Time

func (d *ItemDate) UnmarshalJSON(b []byte) error {
	var rawDate struct {
		Year  int `json:"year"`
		Month int `json:"month"`
		Day   int `json:"day"`
	}
	err := json.Unmarshal(b, &rawDate)
	if err != nil {
		return err
	}
	*d = ItemDate(time.Date(rawDate.Year, time.Month(rawDate.Month), rawDate.Day, 0, 0, 0, 0, time.UTC))
	return nil
}

type DiscTitle struct {
	Disc  int    `json:"disc"`
	Title string `json:"title"`
}

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

type Artist struct {
	ID             SubsonicID `json:"id"`
	Name           string     `json:"name"`
	ArtistImageURL string     `json:"artistImageUrl,omitempty"`
	Starred        *time.Time `json:"starred,omitempty"`
	UserRating     int        `json:"userRating,omitempty"`
	AverageRating  float64    `json:"averageRating,omitempty"`
	Album          []AlbumID3 `json:"album,omitempty"`
}

func (c *Client) GetMusicFolders(ctx context.Context) ([]MusicFolder, error) {
	resp, err := c.getJSON(ctx, "/rest/getMusicFolders.view", nil)
	if err != nil {
		return nil, err
	} else if resp.SubsonicResponse.MusicFolders == nil {
		return nil, nil
	}
	return resp.SubsonicResponse.MusicFolders.MusicFolder, nil
}

func (c *Client) GetIndexes(ctx context.Context, musicFolderID *SubsonicID, ifModifiedSince *time.Time) (*Indexes, error) {
	params := url.Values{}
	if musicFolderID != nil {
		params.Set("musicFolderId", string(*musicFolderID))
	}
	if ifModifiedSince != nil {
		params.Set("ifModifiedSince", ifModifiedSince.Format(time.RFC3339))
	}
	resp, err := c.getJSON(ctx, "/rest/getIndexes.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Indexes, err
}

func (c *Client) GetMusicDirectory(ctx context.Context, id SubsonicID) (*Directory, error) {
	resp, err := c.getJSON(ctx, "/rest/getMusicDirectory.view", url.Values{
		"id": {id.String()},
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Directory, err
}

func (c *Client) GetGenres(ctx context.Context) ([]Genre, error) {
	resp, err := c.getJSON(ctx, "/rest/getGenres.view", nil)
	if err != nil {
		return nil, err
	} else if resp.SubsonicResponse.Genres == nil {
		return nil, nil
	}
	return resp.SubsonicResponse.Genres.Genre, nil
}

func (c *Client) GetArtists(ctx context.Context, musicFolderID *SubsonicID) (*Artists, error) {
	params := url.Values{}
	if musicFolderID != nil {
		params.Set("musicFolderId", string(*musicFolderID))
	}
	resp, err := c.getJSON(ctx, "/rest/getArtists.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Artists, err
}

func (c *Client) GetArtist(ctx context.Context, id SubsonicID) (*Artist, error) {
	resp, err := c.getJSON(ctx, "/rest/getArtist.view", url.Values{
		"id": {id.String()},
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Artist, err
}
