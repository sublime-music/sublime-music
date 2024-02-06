package subsonic

import (
	"context"
	"net/url"
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
//
// If [ReqCreatePlaylist.PlaylistID] is set, the playlist with that ID is
// updated. If it is not set, a new playlist is created.
//
// Note that on old servers (before 1.14.0), the playlist may not be returned
// from the server and might be nil even if there was no error.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#createPlaylist
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/createplaylist/
func (c *Client) CreatePlaylist(ctx context.Context, req ReqCreatePlaylist) (*Playlist, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/createPlaylist.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Playlist, err
}

// ReqUpdatePlaylist is the arguments to [Client.UpdatePlaylist].
type ReqUpdatePlaylist struct {
	PlaylistID        SubsonicID   `url:"playlistId"`                  // The playlist ID.
	Name              *string      `url:"name,omitempty"`              // The human-readable name of the playlist.
	Comment           *string      `url:"comment,omitempty"`           // The playlist comment.
	Public            *bool        `url:"public,omitempty"`            // Whether the playlist is visible to all users.
	SongIDToAdd       []SubsonicID `url:"songIdToAdd,omitempty"`       // Song IDs to add to the playlist.
	SongIndexToRemove []int        `url:"songIndexToRemove,omitempty"` // Song indexes to remove from the playlist.
}

func (c *Client) UpdatePlaylist(ctx context.Context, req ReqUpdatePlaylist) error {
	params, err := MarshalValues(req)
	if err != nil {
		return err
	}
	_, err = c.getJSON(ctx, "/rest/updatePlaylist.view", params)
	return err
}

func (c *Client) DeletePlaylist(ctx context.Context, playlistID SubsonicID) error {
	_, err := c.getJSON(ctx, "/rest/deletePlaylist.view", url.Values{
		"id": {playlistID.String()},
	})
	return err
}
