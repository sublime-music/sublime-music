package subsonic

import (
	"context"
	"net/url"
	"strconv"
)

// GetPlaylists returns all playlists a user is allowed to play.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getPlaylists
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getplaylists/
func (c *Client) GetPlaylists(ctx context.Context, username *string) (*Playlists, error) {
	params := url.Values{}
	if username != nil {
		params.Set("username", *username)
	}
	resp, err := c.getJSON(ctx, "/rest/getPlaylists.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Playlists, nil
}

// GetPlaylist returns a listing of files in a saved playlist.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getPlaylist
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getplaylist/
func (c *Client) GetPlaylist(ctx context.Context, playlistID SubsonicID) (*Playlist, error) {
	resp, err := c.getJSON(ctx, "/rest/getPlaylist.view", url.Values{
		"id": {playlistID.String()},
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Playlist, err
}

// ReqCreatePlaylist is the arguments to [Client.CreatePlaylist].
type ReqCreatePlaylist struct {
	PlaylistID SubsonicID   `url:"playlistId,omitempty"`
	Name       *string      `url:"name,omitempty"` // Required if creating
	SongIDs    []SubsonicID `url:"songId,omitempty"`
}

// CreatePlaylist creates a new playlist or updates an existing one.
func (c *Client) CreatePlaylist(ctx context.Context, name string, songIDs []SubsonicID) (*Playlist, error) {
	resp, err := c.getJSON(ctx, "/rest/createPlaylist.view", url.Values{
		"name":   {name},
		"songId": idsToStrings(songIDs),
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Playlist, err
}

func (c *Client) UpdatePlaylist(ctx context.Context, playlistID SubsonicID, name, comment string, public bool, appendSongIDs []SubsonicID) error {
	_, err := c.getJSON(ctx, "/rest/updatePlaylist.view", url.Values{
		"playlistId":  {playlistID.String()},
		"name":        {name},
		"comment":     {comment},
		"public":      {strconv.FormatBool(public)},
		"songIdToAdd": idsToStrings(appendSongIDs),
	})
	return err
}

func (c *Client) DeletePlaylist(ctx context.Context, playlistID SubsonicID) error {
	_, err := c.getJSON(ctx, "/rest/updatePlaylist.view", url.Values{
		"id": {playlistID.String()},
	})
	return err
}
