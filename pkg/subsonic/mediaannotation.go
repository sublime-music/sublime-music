package subsonic

import (
	"context"
	"fmt"
	"net/url"

	"go.mau.fi/util/jsontime"
)

// ReqStarUnstar is the arguments for [Client.Star] and [Client.Unstar].
type ReqStarUnstar struct {
	// ID are the IDs of the files (songs) or folders (albums/artists) to star.
	ID []SubsonicID `url:"id,omitempty"`
	// AlbumID are the IDs of an albums to star. Use this rather than ID if the
	// client accesses the media collection according to ID3 tags rather than
	// file structure.
	AlbumID []SubsonicID `url:"albumId,omitempty"`
	// ArtistID are the IDs of the artists to star. Use this rather than ID if
	// the client accesses the media collaction according to ID3 tags rather
	// than file structure.
	ArtistID []SubsonicID `url:"artistId,omitempty"`
}

// Star attaches a star to the specified songs, albums, and artists.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#star
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/star/
func (c *Client) Star(ctx context.Context, req ReqStarUnstar) error {
	params, err := MarshalValues(req)
	if err != nil {
		return err
	}
	_, err = c.getJSON(ctx, "/rest/star.view", params)
	return err
}

// Unstar removes a star to the specified songs, albums, and artists.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#unstar
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/unstar/
func (c *Client) Unstar(ctx context.Context, req ReqStarUnstar) error {
	params, err := MarshalValues(req)
	if err != nil {
		return err
	}
	_, err = c.getJSON(ctx, "/rest/unstar.view", params)
	return err
}

// SetRating sets the rating for a music file.
//
// The rating is between 1 and 5 (inclusive). Specify 0 to remove the rating.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#setRating
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/setrating/
func (c *Client) SetRating(ctx context.Context, id SubsonicID, rating int) error {
	_, err := c.getJSON(ctx, "/rest/setRating.view", url.Values{
		"id":     []string{id.String()},
		"rating": []string{fmt.Sprintf("%d", rating)},
	})
	return err
}

// ReqScrobble is the arguments to [Client.Scrobble].
type ReqScrobble struct {
	// ID is the ID of the song to scrobble.
	ID SubsonicID `url:"id"`
	// Time is the time at which the song was listened to. Added in 1.8.0.
	Time jsontime.UnixMilli `url:"time,omitempty"`
	// Submission indicates whether this is a "submission" or a "now playing"
	// notification. Defaults to true.
	Submission *bool `url:"submission,omitempty"`
}

// Scrobble registers the local playback of one or more media files. Typically
// used when playing media that is cached on the client. This operation
// includes the following:
//
//   - "Scrobbles" the media files on last.fm if the user has configured their
//     last.fm credentials on the Subsonic server (Settings > Personal).
//   - Updates the play count and last played timestamp for the media files.
//     (Since 1.11.0).
//   - Makes the media files appear in the "Now playing" page in the web app,
//     and appear in the list of songs returned by [Client.GetNowPlaying]
//     (Since 1.11.0).
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#scrobble
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/scrobble/
func (c *Client) Scrobble(ctx context.Context, req ReqScrobble) error {
	params, err := MarshalValues(req)
	if err != nil {
		return err
	}
	_, err = c.getJSON(ctx, "/rest/scrobble.view", params)
	return err
}
