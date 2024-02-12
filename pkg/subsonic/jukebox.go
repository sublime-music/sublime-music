package subsonic

import "context"

// JukeboxAction is the action to perform on the jukebox.
type JukeboxAction string

const (
	// JukeboxActionGet is the action to get the jukebox status.
	JukeboxActionGet JukeboxAction = "get"
	// JukeboxActionStatus is the action to get the jukebox status. Added in
	// 1.7.0.
	JukeboxActionStatus JukeboxAction = "status"
	// JukeboxActionSet is the action to set the jukebox status. Added in
	// 1.7.0.
	JukeboxActionSet JukeboxAction = "set"
	// JukeboxActionStart is the action to start the jukebox.
	JukeboxActionStart JukeboxAction = "start"
	// JukeboxActionStop is the action to stop the jukebox.
	JukeboxActionStop JukeboxAction = "stop"
	// JukeboxActionSkip is the action to skip the current song.
	JukeboxActionSkip JukeboxAction = "skip"
	// JukeboxActionAdd is the action to add a song to the jukebox playlist.
	JukeboxActionAdd JukeboxAction = "add"
	// JukeboxActionClear is the action to clear the jukebox playlist.
	JukeboxActionClear JukeboxAction = "clear"
	// JukeboxActionRemove is the action to remove a song from the jukebox
	// playlist.
	JukeboxActionRemove JukeboxAction = "remove"
	// JukeboxActionShuffle is the action to shuffle the jukebox playlist.
	JukeboxActionShuffle JukeboxAction = "shuffle"
	// JukeboxActionSetGain is the action to set the jukebox gain. Added in
	// 1.7.0.
	JukeboxActionSetGain JukeboxAction = "setGain"
)

// ReqJukeboxControl is the arguments to [Client.JukeboxControl].
type ReqJukeboxControl struct {
	// Action is the operation to perform.
	Action JukeboxAction `url:"action"`
	// Index is used by skip and remove. Zero-based index of the song to skip to
	// or remove.
	Index *int `url:"index,omitempty"`
	// Offset is used by skip. Start playing this many seconds into the track.
	// Added in 1.7.0.
	Offset *int `url:"offset,omitempty"`
	// ID is the list of song IDs to add to the jukebox playlist, or if
	// [JukeboxActionSet] is used, the song IDs to set as the jukebox playlist.
	ID []SubsonicID `url:"id,omitempty"`
	// Gain is used by setGain to control the playback volume. A float value
	// between 0.0 and 1.0.
	Gain *float64 `url:"gain,omitempty"`
}

// JukeboxControl controls the jukebox, i.e., playback directly on the server's
// audio hardware.
//
// The [JukeboxStatus] will be returned on success unless the action is
// [JukeboxActionGet], in which case the [JukeboxPlaylist] will be returned.
//
// Note: The user must be authorized to control the jukebox (see Settings >
// Users > User is allowed to play files in jukebox mode).
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#jukeboxControl
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/jukeboxcontrol/
func (c *Client) JukeboxControl(ctx context.Context, req ReqJukeboxControl) (*JukeboxStatus, *JukeboxPlaylist, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/jukeboxControl.view", params)
	if err != nil {
		return nil, nil, err
	}
	return resp.SubsonicResponse.JukeboxStatus, resp.SubsonicResponse.JukeboxPlaylist, nil
}
