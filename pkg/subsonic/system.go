package subsonic

import (
	"context"
	"time"
)

type License struct {
	Valid          bool      `json:"valid"`
	Email          string    `json:"email"`
	LicenseExpires time.Time `json:"licenseExpires"`
	TrialExpires   time.Time `json:"trialExpires"`
}

type OpenSubsonicExtension struct {
	Name     string `json:"name"`
	Versions []int  `json:"versions"`
}

func (c *Client) Ping(ctx context.Context) (*SubsonicResponse, error) {
	resp, err := c.getJSON(ctx, "/rest/ping.view", nil)
	return resp.SubsonicResponse, err
}

func (c *Client) GetLicense(ctx context.Context) (*License, error) {
	resp, err := c.getJSON(ctx, "/rest/getLicense.view", nil)
	return resp.SubsonicResponse.License, err
}

func (c *Client) GetOpenSubsonicExtensions(ctx context.Context) ([]OpenSubsonicExtension, error) {
	if !c.openSubsonic {
		return nil, ErrServerDoesNotSupportOpenSubsonic
	}
	resp, err := c.getJSON(ctx, "/rest/getOpenSubsonicExtensions.view", nil)
	return resp.SubsonicResponse.OpenSubsonicExtensions, err
}
