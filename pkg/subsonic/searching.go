package subsonic

import "context"

// ReqSearch is the arguments to [Client.Search2] or [Client.Search3].
type ReqSearch struct {
	// Query is the search query.
	Query string `url:"query"`
	// ArtistCount is the maximum number of artists to return. Default 20.
	ArtistCount *int `url:"artistCount,omitempty"`
	// ArtistOffset is the search result offset for artists. Used for paging.
	// Default 0.
	ArtistOffset *int `url:"artistOffset,omitempty"`
	// AlbumCount is the maximum number of albums to return. Default 20.
	AlbumCount *int `url:"albumCount,omitempty"`
	// AlbumOffset is the search result offset for albums. Used for paging.
	// Default 0.
	AlbumOffset *int `url:"albumOffset,omitempty"`
	// SongCount is the maximum number of songs to return. Default 20.
	SongCount *int `url:"songCount,omitempty"`
	// SongOffset is the search result offset for songs. Used for paging.
	SongOffset *int `url:"songOffset,omitempty"`
	// MusicFolderID restricts the server to return albums in the music folder
	// with the given ID. Added in 1.12.0.
	MusicFolderID *SubsonicID `url:"musicFolderId,omitempty"`
}

// Search2 returns a listing of files matching the given search criteria.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#search2
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/search2/
func (c *Client) Search2(ctx context.Context, req ReqSearch) (*SearchResult2, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/search2.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.SearchResult2, nil
}

// Search3 returns a listing of files matching the given search criteria. This
// is the same as [Client.Search2] except it organizes music according to ID3
// tags.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#search3
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/search3/
func (c *Client) Search3(ctx context.Context, req ReqSearch) (*SearchResult3, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/search3.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.SearchResult3, nil
}
