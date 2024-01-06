package subsonic

import (
	"context"
)

// Ping tests connectivity with the server.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#ping
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/ping/
func (c *Client) Ping(ctx context.Context) (*SubsonicResponse, error) {
	resp, err := c.getJSON(ctx, "/rest/ping.view", nil)
	return resp.SubsonicResponse, err
}

// GetLicense gets details about the software license.
//
// Docs: [Subsonic], [OpenSubsonic]
//
// [Subsonic]: http://www.subsonic.org/pages/api.jsp#getLicense
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getlicense/
func (c *Client) GetLicense(ctx context.Context) (*License, error) {
	resp, err := c.getJSON(ctx, "/rest/getLicense.view", nil)
	return resp.SubsonicResponse.License, err
}

// GetOpenSubsonicExtensions gets a list of the OpenSubsonic extensions
// supported by this server.
//
// Docs: [OpenSubsonic]
//
// [OpenSubsonic]: https://opensubsonic.netlify.app/docs/endpoints/getopensubsonicextensions/
func (c *Client) GetOpenSubsonicExtensions(ctx context.Context) ([]OpenSubsonicExtension, error) {
	if !c.openSubsonic {
		return nil, ErrServerDoesNotSupportOpenSubsonic
	}
	resp, err := c.getJSON(ctx, "/rest/getOpenSubsonicExtensions.view", nil)
	return resp.SubsonicResponse.OpenSubsonicExtensions, err
}
