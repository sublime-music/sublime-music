package subsonic

import (
	"context"
	"net/url"
	"time"
)

// GetMusicFolders returns all configured top-level music folders.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getMusicFolders
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getmusicfolders/
func (c *Client) GetMusicFolders(ctx context.Context) ([]MusicFolder, error) {
	resp, err := c.getJSON(ctx, "/rest/getMusicFolders.view", nil)
	if err != nil {
		return nil, err
	} else if resp.SubsonicResponse.MusicFolders == nil {
		return nil, nil
	}
	return resp.SubsonicResponse.MusicFolders.MusicFolder, nil
}

// ReqGetIndexes is a request to [GetIndexes].
type ReqGetIndexes struct {
	// MusicFolderID (if specified) restricts the server to return albums in
	// the music folder with the given ID.
	MusicFolderID *SubsonicID `url:"musicFolderId,omitempty"`
	// IfModifiedSince (if specified) tells the server to only return a result
	// if the artist collection has changed since the given time (in
	// milliseconds since 1 Jan 1970).
	IfModifiedSince *time.Time `url:"ifModifiedSince,omitempty"`
}

// GetIndexes returns an indexed structure of all artists.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getIndexes
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getindexes/
func (c *Client) GetIndexes(ctx context.Context, req ReqGetIndexes) (*Indexes, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/getIndexes.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Indexes, nil
}

// GetMusicDirectory returns a listing of all files in a music directory.
// Typically used to get list of albums for an artist, or list of songs for an
// album.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getMusicDirectory
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getmusicdirectory/
func (c *Client) GetMusicDirectory(ctx context.Context, id SubsonicID) (*Directory, error) {
	resp, err := c.getJSON(ctx, "/rest/getMusicDirectory.view", url.Values{
		"id": {id.String()},
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Directory, nil
}

// GetGenres returns all genres.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getGenres
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getgenres/
func (c *Client) GetGenres(ctx context.Context) ([]Genre, error) {
	resp, err := c.getJSON(ctx, "/rest/getGenres.view", nil)
	if err != nil {
		return nil, err
	} else if resp.SubsonicResponse.Genres == nil {
		return nil, nil
	}
	return resp.SubsonicResponse.Genres.Genre, nil
}

// GetArtists returns an indexed structure of all artists, organized according
// to ID3 tags.
//
// GetArtists is the ID3 equivalent of [Client.GetIndexes].
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getArtists
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getartists/
func (c *Client) GetArtists(ctx context.Context, musicFolderID *SubsonicID) (*ArtistsID3, error) {
	params := url.Values{}
	if musicFolderID != nil {
		params.Set("musicFolderId", string(*musicFolderID))
	}
	resp, err := c.getJSON(ctx, "/rest/getArtists.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Artists, nil
}

// GetArtist returns details for an artist, including a list of albums. This
// method organizes music according to ID3 tags.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getArtist
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getartist/
func (c *Client) GetArtist(ctx context.Context, id SubsonicID) (*Artist, error) {
	resp, err := c.getJSON(ctx, "/rest/getArtist.view", url.Values{
		"id": {id.String()},
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Artist, nil
}

// GetAlbum returns details for an album, including a list of songs. This
// method organizes music according to ID3 tags.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getAlbum
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getalbum/
func (c *Client) GetAlbum(ctx context.Context, id SubsonicID) (*AlbumID3, error) {
	resp, err := c.getJSON(ctx, "/rest/getAlbum.view", url.Values{
		"id": {id.String()},
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Album, nil
}

// GetSong returns details for a song.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getSong
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getsong/
func (c *Client) GetSong(ctx context.Context, id SubsonicID) (*Child, error) {
	resp, err := c.getJSON(ctx, "/rest/getSong.view", url.Values{
		"id": {id.String()},
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Song, nil
}

// GetVideos returns all video files.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getVideos
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getvideos/
func (c *Client) GetVideos(ctx context.Context) ([]Child, error) {
	resp, err := c.getJSON(ctx, "/rest/getVideos.view", nil)
	if err != nil {
		return nil, err
	} else if resp.SubsonicResponse.Videos == nil {
		return nil, nil
	}
	return resp.SubsonicResponse.Videos.Video, nil
}

// GetVideoInfo returns details for a video.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getVideoInfo
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getvideoinfo/
func (c *Client) GetVideoInfo(ctx context.Context, id SubsonicID) (*VideoInfo, error) {
	resp, err := c.getJSON(ctx, "/rest/getVideoInfo.view", url.Values{
		"id": {id.String()},
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.VideoInfo, nil
}

// ReqGetArtistInfo is the arguments to [Client.GetArtistInfo] or
// [Client.GetArtistInfo2].
type ReqGetArtistInfo struct {
	// ID is the ID of the artist to get info for.
	ID SubsonicID `url:"id"`
	// Conut is the number of similar artists to return. Default 20.
	Count *int `url:"count,omitempty"`
	// IncludeNotPresent indicates whether to return artists that are not
	// present in the media library. Default false.
	IncludeNotPresent *bool `url:"includeNotPresent,omitempty"`
}

// GetArtistInfo returns artist info with biography, image URLs and similar
// artists, using data from last.fm.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getArtistInfo
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getartistinfo/
func (c *Client) GetArtistInfo(ctx context.Context, req ReqGetArtistInfo) (*ArtistInfo, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/getArtistInfo.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.ArtistInfo, nil
}

// GetArtistInfo2 returns artist info with biography, image URLs and similar
// artists, using data from last.fm.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getArtistInfo
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getartistinfo/
func (c *Client) GetArtistInfo2(ctx context.Context, req ReqGetArtistInfo) (*ArtistInfo, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/getArtistInfo2.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.ArtistInfo, nil
}

// GetAlbumInfo returns album notes, image URLs etc, using data from last.fm.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getAlbumInfo
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getalbuminfo/
func (c *Client) GetAlbumInfo(ctx context.Context, id SubsonicID) (*AlbumInfo, error) {
	resp, err := c.getJSON(ctx, "/rest/getAlbumInfo.view", url.Values{
		"id": {id.String()},
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.AlbumInfo, nil
}

// GetAlbumInfo2 returns album notes, image URLs etc, using data from last.fm.
// This is the same as [Client.GetAlbumInfo] except it organizes music
// according to ID3 tags.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getAlbumInfo2
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getalbuminfo2/
func (c *Client) GetAlbumInfo2(ctx context.Context, id SubsonicID) (*AlbumInfo, error) {
	resp, err := c.getJSON(ctx, "/rest/getAlbumInfo2.view", url.Values{
		"id": {id.String()},
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.AlbumInfo, nil
}

// ReqGetSimilarSongs is the arguments to [Client.GetSimilarSongs] or
// [Client.GetSimilarSongs2].
type ReqGetSimilarSongs struct {
	// ID is the artist, album or song ID to get similar songs for.
	ID SubsonicID `url:"id"`
	// Count is the max number of songs to return. Default 50.
	Count *int `url:"count,omitempty"`
}

// GetSimilarSongs returns a random collection of songs from the given artist
// and similar artists, using data from last.fm. Typically used for artist
// radio features.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getSimilarSongs
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getsimilarsongs/
func (c *Client) GetSimilarSongs(ctx context.Context, req ReqGetSimilarSongs) ([]Child, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/getSimilarSongs.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.SimilarSongs.Song, nil
}

// GetSimilarSongs2 returns a random collection of songs from the given artist
// and similar artists, using data from last.fm. Typically used for artist
// radio features. This is the same as [GetSimilarSongs] except it organizes
// music according to ID3 tags.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getSimilarSongs2
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getsimilarsongs2/
func (c *Client) GetSimilarSongs2(ctx context.Context, req ReqGetSimilarSongs) ([]Child, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/getSimilarSongs2.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.SimilarSongs2.Song, nil
}

// ReqGetTopSongs is the arguments to [Client.GetTopSongs].
type ReqGetTopSongs struct {
	// Artist is the artist name.
	Artist string `url:"artist"`
	// Count is the max number of songs to return. Default 50.
	Count *int `url:"count,omitempty"`
}

// GetTopSongs returns top songs for the given artist using data from last.fm.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getTopSongs
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/gettopsongs/
func (c *Client) GetTopSongs(ctx context.Context, req ReqGetTopSongs) ([]Child, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/getTopSongs.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.TopSongs.Song, nil
}
