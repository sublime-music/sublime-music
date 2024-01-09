package subsonic

type SubsonicResponseStatus string

const (
	SubsonicResponseStatusOk     SubsonicResponseStatus = "ok"
	SubsonicResponseStatusFailed SubsonicResponseStatus = "failed"
)

// SubsonicResponse is the top-level response object from the Subsonic API.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/responses/subsonic-response/
type SubsonicResponse struct {
	Status        string         `json:"status"`
	Version       string         `json:"version"`
	Type          string         `json:"type"`
	ServerVersion string         `json:"serverVersion"`
	OpenSubsonic  bool           `json:"openSubsonic"`
	Error         *SubsonicError `json:"error,omitempty"`

	// System
	License                *License
	OpenSubsonicExtensions []OpenSubsonicExtension `json:"openSubsonicExtensions,omitempty"`

	// Browsing
	MusicFolders *MusicFolders `json:"musicFolders"`
	Indexes      *Indexes      `json:"indexes"`
	Directory    *Directory    `json:"directory"`
	Genres       *Genres       `json:"genres"`
	Artists      *Artists      `json:"artists"`
	Artist       *Artist       `json:"artist"`
	Album        *AlbumID3     `json:"album"`
	Song         *Song         `json:"song"`
	Videos       *Videos       `json:"videos"`

	Playlists *Playlists `json:"playlists,omitempty"`
	Playlist  *Playlist  `json:"playlist,omitempty"`
}

type Response struct {
	SubsonicResponse *SubsonicResponse `json:"subsonic-response,omitempty"`
}
