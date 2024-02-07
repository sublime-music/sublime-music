package subsonic

import (
	"context"
	"io"
	"net/url"
)

// ReqStream is the arguments to [Client.Stream].
type ReqStream struct {
	// ID is the ID of the file to stream.
	ID SubsonicID `url:"id"`
	// MaxBitRate asks the server to attempt to limit the bitrate to this value
	// (in kilobits per second), if specified. If set to zero, no limit is
	// imposed. Added in 1.2.0.
	MaxBitRate *int `url:"maxBitRate,omitempty"`
	// Format specifies the preferred target format (e.g., "mp3" or "flv") in
	// case there are multiple applicable transcodings. Starting with 1.9.0 you
	// can use the special value "raw" to disable transcoding. Added in 1.6.0.
	Format *string `url:"format,omitempty"`
	// TimeOffset (if nonzero specified) tells the server to start streaming at
	// the given offset (in seconds) into the media.
	TimeOffset int64 `url:"timeOffset,omitempty"`
	// Size is the requested video size specified as WxH, for instance
	// "640x480". Only applicable to video streaming.
	Size string `url:"size,omitempty"`
	// EstimateContentLength requests that the server includes the
	// Content-Length HTTP header with the estimated value for transcoded or
	// downsampled media.
	EstimateContentLength bool `url:"estimateContentLength,omitempty"`
	// Converted is only applicable to video streaming. Subsonic can optimize
	// videos for streaming by converting them to MP4. If a conversion exists
	// for the video in question, then setting this parameter to "true" will
	// cause the converted video to be returned instead of the original. Added
	// in 1.14.0.
	Converted bool `url:"converted,omitempty"`
}

// Stream streams the given media file. This returns an [io.Reader]. It is the
// responsibility of the caller to close the reader.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#stream
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/stream/
func (c *Client) Stream(ctx context.Context, req ReqStream) (io.Reader, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.get(ctx, "/rest/stream.view", params)
	return resp.Body, err
}

// Download downloads the given media file. Similar to [Client.Stream], but
// this method returns the original media data without transcoding or
// downsampling.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#download
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/download/
func (c *Client) Download(ctx context.Context, id SubsonicID) ([]byte, error) {
	resp, err := c.get(ctx, "/rest/download.view", url.Values{
		"id": {id.String()},
	})
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	return io.ReadAll(resp.Body)
}

// HLS is not implemented
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#hls
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/hls/

// ReqGetCaptions is the arguments to [Client.GetCaptions].
type ReqGetCaptions struct {
	// ID is the ID of the video.
	ID SubsonicID `url:"id"`
	// Format is the preferred captions format ("srt" or "vtt").
	Format string `url:"format,omitempty"`
}

// GetCaptions returns captions (subtitles) for a video. Use
// [Client.GetVideoInfo] to get a list of available captions. This returns the
// raw captions in the format specified.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getCaptions
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getcaptions/
func (c *Client) GetCaptions(ctx context.Context, req ReqGetCaptions) ([]byte, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.get(ctx, "/rest/getCaptions.view", params)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	return io.ReadAll(resp.Body)
}

// ReqGetCoverArt is the arguments to [Client.GetCoverArt].
type ReqGetCoverArt struct {
	// ID is the ID of a song, album or artist to get cover art for.
	ID SubsonicID `url:"id"`
	// Size (if specified) tells the server to scale the image to this size.
	Size int `url:"size,omitempty"`
}

// GetCoverArt returns a cover art image.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getCoverArt
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getcoverart/
func (c *Client) GetCoverArt(ctx context.Context, req ReqGetCoverArt) ([]byte, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.get(ctx, "/rest/getCoverArt.view", params)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	return io.ReadAll(resp.Body)
}

// ReqGetLyrics is the arguments to [Client.GetLyrics].
type ReqGetLyrics struct {
	// Artist is the artist name.
	Artist string `url:"artist,omitempty"`
	// Title is the song title.
	Title string `url:"title,omitempty"`
}

// GetLyrics searches for and returns lyrics for a given song.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getLyrics
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getlyrics/
func (c *Client) GetLyrics(ctx context.Context, req ReqGetLyrics) (*Lyrics, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/getLyrics.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Lyrics, nil
}

// GetAvatar returns the avatar (personal image) for a user.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getAvatar
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getavatar/
func (c *Client) GetAvatar(ctx context.Context, username string) ([]byte, error) {
	resp, err := c.get(ctx, "/rest/getCoverArt.view", url.Values{
		"username": []string{username},
	})
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	return io.ReadAll(resp.Body)
}
