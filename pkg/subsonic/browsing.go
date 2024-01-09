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

// GetIndexes returns an indexed structure of all artists.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getIndexes
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getindexes/
func (c *Client) GetIndexes(ctx context.Context, musicFolderID *SubsonicID, ifModifiedSince *time.Time) (*Indexes, error) {
	params := url.Values{}
	if musicFolderID != nil {
		params.Set("musicFolderId", string(*musicFolderID))
	}
	if ifModifiedSince != nil {
		params.Set("ifModifiedSince", ifModifiedSince.Format(time.RFC3339))
	}
	resp, err := c.getJSON(ctx, "/rest/getIndexes.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Indexes, err
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
	return resp.SubsonicResponse.Directory, err
}

// GetGenres returns all genres
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
func (c *Client) GetArtists(ctx context.Context, musicFolderID *SubsonicID) (*Artists, error) {
	params := url.Values{}
	if musicFolderID != nil {
		params.Set("musicFolderId", string(*musicFolderID))
	}
	resp, err := c.getJSON(ctx, "/rest/getArtists.view", params)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Artists, err
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
	return resp.SubsonicResponse.Artist, err
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
	return resp.SubsonicResponse.Album, err
}

// GetSong returns details for a song.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getSong
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getsong/
func (c *Client) GetSong(ctx context.Context, id SubsonicID) (*Song, error) {
	resp, err := c.getJSON(ctx, "/rest/getSong.view", url.Values{
		"id": {id.String()},
	})
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Song, err
}

// getVideoInfo getArtistInfo getArtistInfo2 getAlbumInfo getAlbumInfo2 getSimilarSongs getSimilarSongs2 getTopSongs

// GetVideos returns all video files.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getVideos
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getvideos/
func (c *Client) GetVideos(ctx context.Context) ([]VideoInfo, error) {
	resp, err := c.getJSON(ctx, "/rest/getVideos.view", nil)
	if err != nil {
		return nil, err
	} else if resp.SubsonicResponse.Videos == nil {
		return nil, nil
	}
	return resp.SubsonicResponse.Videos.Video, nil
}
