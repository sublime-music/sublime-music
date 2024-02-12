package subsonic

import (
	"context"
	"io"
	"net/url"
	"strconv"
)

// ReqGetPodcasts is the arguments to [Client.GetPodcasts].
type ReqGetPodcasts struct {
	// ID is the ID of a single Podcast channel to retrieve. Added in 1.9.0.
	ID SubsonicID `url:"id,omitempty"`
	// IncludeEpisodes is whether to include episodes in the response. Defaults
	// to true. Added in 1.9.0.
	IncludeEpisodes *bool `url:"includeEpisodes,omitempty"`
}

// GetPodcasts returns all Podcast channels the server subscribes to, and
// (optionally) their episodes.
//
// This method can also be used to return details for only one channel using
// the [ReqGetPodcasts.ID] parameter. A typical use case for this method would
// be to first retrieve all channels without episodes, and then retrieve all
// episodes for the single channel the user selects.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getPodcasts
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getpodcasts/
func (c *Client) GetPodcasts(ctx context.Context, req ReqGetPodcasts) (*Podcasts, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/getPodcasts.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Podcasts, nil
}

// GetNewestPodcasts returns the most recently published Podcast episodes.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getNewestPodcasts
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getnewestpodcasts/
func (c *Client) GetNewestPodcasts(ctx context.Context, count *int) (*NewestPodcasts, error) {
	params := url.Values{}
	if count != nil {
		params.Add("count", strconv.Itoa(*count))
	}
	resp, err := c.getJSON(ctx, "/rest/getNewestPodcasts.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.NewestPodcasts, nil
}

// RefreshPodcasts requests the server to check for new Podcast episodes.
//
// Note: The user must be authorized for Podcast administration (see Settings >
// Users > User is allowed to administrate Podcasts).
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#refreshPodcasts
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/refreshpodcasts/
func (c *Client) RefreshPodcasts(ctx context.Context) error {
	_, err := c.getJSON(ctx, "/rest/refreshPodcasts.view", nil)
	return err
}

// CreatePodcastChannel adds a new Podcast channel.
//
// Note: The user must be authorized for Podcast administration (see Settings >
// Users > User is allowed to administrate Podcasts).
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#createPodcastChannel
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/createpodcastchannel/
func (c *Client) CreatePodcastChannel(ctx context.Context, uri string) error {
	_, err := c.getJSON(ctx, "/rest/createPodcastChannel.view", url.Values{
		"url": {uri},
	})
	return err
}

// DeletePodcastChannel deletes a Podcast channel.
//
// Note: The user must be authorized for Podcast administration (see Settings >
// Users > User is allowed to administrate Podcasts).
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#deletePodcastChannel
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/deletepodcastchannel/
func (c *Client) DeletePodcastChannel(ctx context.Context, id SubsonicID) error {
	_, err := c.getJSON(ctx, "/rest/deletePodcastChannel.view", url.Values{
		"id": {id.String()},
	})
	return err
}

// DeletePodcastEpisode deletes a Podcast episode.
//
// Note: The user must be authorized for Podcast administration (see Settings >
// Users > User is allowed to administrate Podcasts).
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#deletePodcastEpisode
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/deletepodcastepisode/
func (c *Client) DeletePodcastEpisode(ctx context.Context, id SubsonicID) error {
	_, err := c.getJSON(ctx, "/rest/deletePodcastEpisode.view", url.Values{
		"id": {id.String()},
	})
	return err
}

// DownloadPodcastEpisode downloads a Podcast episode.
//
// Note: The user must be authorized for Podcast administration (see Settings >
// Users > User is allowed to administrate Podcasts).
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#downloadPodcastEpisode
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/downloadpodcastepisode/
func (c *Client) DownloadPodcastEpisode(ctx context.Context, id SubsonicID) ([]byte, error) {
	resp, err := c.get(ctx, "/rest/downloadPodcastEpisode.view", url.Values{
		"id": {id.String()},
	})
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	return io.ReadAll(resp.Body)
}
