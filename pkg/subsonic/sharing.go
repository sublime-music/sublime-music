package subsonic

import (
	"context"
	"errors"
	"fmt"
	"net/url"

	"go.mau.fi/util/jsontime"
)

// GetShares returns information about shared media this user is allowed to
// manage.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getShares
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getshares/
func (c *Client) GetShares(ctx context.Context) (*Shares, error) {
	resp, err := c.getJSON(ctx, "/rest/getShares.view", nil)
	if err != nil {
		return nil, err
	}
	return resp.SubsonicResponse.Shares, nil
}

// ReqCreateShare is the arguments to [Client.CreateShare].
type ReqCreateShare struct {
	// ID is the list of song, album or video IDs to share.
	ID []SubsonicID `url:"id"`
	// Description is a user-defined description that will be displayed to
	// people visiting the shared media.
	Description string `url:"description,omitempty"`
	// Expires is the time at which the share expires.
	Expires jsontime.UnixMilli `url:"expires,omitempty"`
}

// CreateShare creates a public URL that can be used by anyone to stream music
// or video from the Subsonic server. The URL is short and suitable for posting
// on Facebook, Twitter etc.
//
// Note: The user must be authorized to share (see Settings > Users > User is
// allowed to share files with anyone).
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#createShare
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/createshare/
func (c *Client) CreateShare(ctx context.Context, req ReqCreateShare) (*Share, error) {
	params, err := MarshalValues(req)
	if err != nil {
		return nil, err
	}
	resp, err := c.getJSON(ctx, "/rest/createShare.view", params)
	if err != nil {
		return nil, err
	}
	if resp.SubsonicResponse.Shares == nil {
		return nil, errors.New("share not present in response")
	}
	if n := len(resp.SubsonicResponse.Shares.Share); n != 1 {
		return nil, fmt.Errorf("unexpected number of share objects (%d) returned", n)
	}
	return &resp.SubsonicResponse.Shares.Share[0], nil
}

// ReqUpdateShare is the arguments to [Client.UpdateShare].
type ReqUpdateShare struct {
	// ID is the ID of the share to update.
	ID SubsonicID `url:"id"`
	// Description is a user-defined description that will be displayed to
	// people visiting the shared media.
	Description string `url:"description,omitempty"`
	// Expires is the time at which the share expires.
	Expires jsontime.UnixMilli `url:"expires,omitempty"`
}

// UpdateShare updates the description and/or expiration date for an existing
// share.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#updateShare
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/updateshare/
func (c *Client) UpdateShare(ctx context.Context, req ReqUpdateShare) error {
	params, err := MarshalValues(req)
	if err != nil {
		return err
	}
	_, err = c.getJSON(ctx, "/rest/updateShare.view", params)
	return err
}

// DeleteShare deletes an existing share.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#deleteShare
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/deleteshare/
func (c *Client) DeleteShare(ctx context.Context, id SubsonicID) error {
	_, err := c.getJSON(ctx, "/rest/deleteShare.view", url.Values{
		"id": []string{id.String()},
	})
	return err
}
