package subsonic

import (
	"context"
	"net/url"
)

type AlbumListType string

const (
	AlbumListTypeRandom               AlbumListType = "random"
	AlbumListTypeNewest               AlbumListType = "newest"
	AlbumListTypeHighest              AlbumListType = "highest"
	AlbumListTypeFrequest             AlbumListType = "frequent"
	AlbumListTypeRecent               AlbumListType = "recent"
	AlbumListTypeAlphabeticalByName   AlbumListType = "alphabeticalByName"   // Added in 1.8.0
	AlbumListTypeAlphabeticalByArtist AlbumListType = "alphabeticalByArtist" // Added in 1.8.0
	AlbumListTypeStarred              AlbumListType = "starred"              // Added in 1.8.0
	AlbumListTypeByYear               AlbumListType = "byYear"               // Added in 1.10.1
	AlbumListTypeByGenre              AlbumListType = "byGenre"              // Added in 1.10.1
)

// ReqGetAlbumList is the arguments to [Client.GetAlbumList] or
// [Client.GetAlbumList2].
type ReqGetAlbumList struct {
	// Type is the list type.
	Type AlbumListType `url:"type"`
	// Size is the number of albums to return. Max 500.
	Size *int `url:"size,omitempty"`
	// Offset is the list offset. Useful if you for example want to page
	// through the list of newest albums.
	Offset *int `url:"offset,omitempty"`
	// FromYear is the first year in the range. If fromYear > toYear a reverse
	// chronological list is returned.
	FromYear *int `url:"fromYear,omitempty"`
	// ToYear is the last year in the range.
	ToYear *int `url:"toYear,omitempty"`
	// Genre is the name of the genre, e.g., "Rock".
	Genre *string `url:"genre,omitempty"`
	// MusicFolderID restricts the server to return albums in the music folder
	// with the given ID. Added in 1.11.0.
	MusicFolderID *SubsonicID `url:"musicFolderId,omitempty"`
}

// GetAlbumList returns a list of random, newest, highest rated etc. albums.
// Similar to the album lists on the home page of the Subsonic web interface.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getAlbumList
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getalbumlist/
func (c *Client) GetAlbumList(ctx context.Context, req ReqGetAlbumList) (*AlbumList, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/getAlbumList.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.AlbumList, nil
}

// GetAlbumList2 returns a list of random, newest, highest rated etc. albums
// organized by ID3 tags.
//
// This is the same as [Client.GetAlbumList] except it organizes music
// according to ID3 tags.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getAlbumList2
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getalbumlist2/
func (c *Client) GetAlbumList2(ctx context.Context, req ReqGetAlbumList) (*AlbumList2, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/getAlbumList2.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.AlbumList2, nil
}

// ReqGetRandomSongs is the arguments to [Client.GetRandomSongs].
type ReqGetRandomSongs struct {
	// Size is the number of songs to return. Max 500.
	Size *int `url:"size,omitempty"`
	// Genre restricts the server to only return songs belonging to this genre.
	Genre *string `url:"genre,omitempty"`
	// FromYear restricts the server to only return songs published after or in
	// this year.
	FromYear *int `url:"fromYear,omitempty"`
	// ToYear restricts the server to only return songs published before or in
	// this year.
	ToYear *int `url:"toYear,omitempty"`
	// MusicFolderID restricts the server to return albums in the music folder
	// with the given ID.
	MusicFolderID *SubsonicID `url:"musicFolderId,omitempty"`
}

// GetRandomSongs returns random songs matching the given criteria.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getRandomSongs
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getrandomsongs/
func (c *Client) GetRandomSongs(ctx context.Context, req ReqGetRandomSongs) (*Songs, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/getRandomSongs.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.RandomSongs, nil
}

// ReqGetSongsByGenre is the arguments to [Client.GetSongsByGenre].
type ReqGetSongsByGenre struct {
	// Genre is the genre to return songs for.
	Genre string `url:"genre"`
	// Count is the maximum number of songs to return. Max 500.
	Count *int `url:"count,omitempty"`
	// Offset is the list offset. Useful if you want to page through the songs
	// in a genre.
	Offset *int `url:"offset,omitempty"`
	// MusicFolderID restricts the server to return albums in the music folder
	// with the given ID. Added in 1.12.0.
	MusicFolderID *SubsonicID `url:"musicFolderId,omitempty"`
}

// GetSongsByGenre returns songs in a given genre.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getSongsByGenre
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getsongsbygenre/
func (c *Client) GetSongsByGenre(ctx context.Context, req ReqGetSongsByGenre) (*Songs, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/getSongsByGenre.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.SongsByGenre, nil
}

// GetNowPlaying returns what is currently being played by all users.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getNowPlaying
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getnowplaying/
func (c *Client) GetNowPlaying(ctx context.Context) (*NowPlaying, error) {
	resp, err := c.getJSON(ctx, "/rest/getNowPlaying.view", nil)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.NowPlaying, nil
}

// GetStarred returns the list of starred songs, albums, and artists.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getStarred
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getstarred/
func (c *Client) GetStarred(ctx context.Context, musicFolderID *SubsonicID) (*Starred, error) {
	params := url.Values{}
	if musicFolderID != nil {
		params.Set("musicFolderId", musicFolderID.String())
	}
	resp, err := c.getJSON(ctx, "/rest/getStarred.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Starred, nil
}

// GetStarred2 returns the list of starred songs, albums, and artists organized
// by ID3 tags.
//
// This is the same as [Client.GetStarred] except it organizes music according
// to ID3 tags.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getStarred2
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getstarred2/
func (c *Client) GetStarred2(ctx context.Context, musicFolderID *SubsonicID) (*Starred2, error) {
	params := url.Values{}
	if musicFolderID != nil {
		params.Set("musicFolderId", musicFolderID.String())
	}
	resp, err := c.getJSON(ctx, "/rest/getStarred2.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Starred2, nil
}
