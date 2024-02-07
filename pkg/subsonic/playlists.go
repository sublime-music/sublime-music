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
	// PlaylistID is the playlist ID to edit or empty if nothing to edit.
	PlaylistID SubsonicID `url:"playlistId,omitempty"`
	// Name is the name of the playlist. Required if creating.
	Name string `url:"name,omitempty"`
	// SongIDs are the IDs of the songs in the playlist.
	SongIDs []SubsonicID `url:"songId,omitempty"`
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
	// PlaylistID is the playlist ID.
	PlaylistID SubsonicID `url:"playlistId"`
	// Name is the human-readable name of the playlist.
	Name *string `url:"name,omitempty"`
	// Comment is the playlist comment.
	Comment *string `url:"comment,omitempty"`
	// Public is whether the playlist is visible to all users.
	Public *bool `url:"public,omitempty"`
	// SongIDsToAdd are the song IDs to add to the playlist.
	SongIDToAdd []SubsonicID `url:"songIdToAdd,omitempty"`
	// SongIndexToRemove are the indexes of the songs to remove from the
	// playlist.
	SongIndexToRemove []int `url:"songIndexToRemove,omitempty"`
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
