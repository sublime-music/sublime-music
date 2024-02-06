package subsonic

import "context"

type ReqSearch struct {
	Query         string      `url:"query"`
	ArtistCount   *int        `url:"artistCount,omitempty"`
	ArtistOffset  *int        `url:"artistOffset,omitempty"`
	AlbumCount    *int        `url:"albumCount,omitempty"`
	AlbumOffset   *int        `url:"albumOffset,omitempty"`
	SongCount     *int        `url:"songCount,omitempty"`
	SongOffset    *int        `url:"songOffset,omitempty"`
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
