package subsonic

import (
	"context"
	"net/url"
	"strconv"
)

func (c *Client) GetPlaylists(ctx context.Context) ([]Playlist, error) {
	resp, err := c.getJSON(ctx, "/rest/getPlaylists.view", nil)
	if err != nil {
		return nil, err
	} else if resp.SubsonicResponse.Playlists == nil {
		return nil, nil
	}

	return resp.SubsonicResponse.Playlists.Playlist, nil
}

func (c *Client) GetPlaylist(ctx context.Context, playlistID SubsonicID) (*Playlist, error) {
	resp, err := c.getJSON(ctx, "/rest/getPlaylist.view", url.Values{
		"id": {playlistID.String()},
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Playlist, err
}

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

func (c *Client) ReorderPlaylistSongs(ctx context.Context, playlistID SubsonicID, newSongOrder []SubsonicID) (*Playlist, error) {
	resp, err := c.getJSON(ctx, "/rest/createPlaylist.view", url.Values{
		"playlistId": {playlistID.String()},
		"songId":     idsToStrings(newSongOrder),
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
