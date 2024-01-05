package subsonic

import (
	"bytes"
	"context"
	"crypto/md5"
	"crypto/tls"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"

	"go.mau.fi/util/random"
)

type Client struct {
	hostname    *url.URL
	username    string
	password    string
	useSaltAuth bool

	client       *http.Client
	version      string
	openSubsonic bool

	serverAvailable bool
}

func NewClient(hostname, username, password string, verifyCert, useSaltAuth bool) (*Client, error) {
	client := &http.Client{}
	if !verifyCert {
		client.Transport = &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}}
	}

	url, err := url.Parse(hostname)
	if err != nil {
		return nil, err
	}

	return &Client{
		hostname:    url,
		username:    username,
		password:    password,
		useSaltAuth: useSaltAuth,

		client:  client,
		version: "1.8.0",
	}, nil
}

func (c *Client) get(ctx context.Context, path string, params url.Values) (*http.Response, error) {
	salt := random.String(20)
	hash := md5.Sum([]byte(c.password + salt))
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.hostname.JoinPath(path).String(), nil)
	if err != nil {
		return nil, err
	}

	if params == nil {
		params = url.Values{}
	}
	params.Set("v", c.version)
	params.Set("c", "Sublime Music")
	params.Set("f", "json")

	// Authentication
	params.Set("u", c.username)
	if c.useSaltAuth {
		params.Set("t", hex.EncodeToString(hash[:]))
		params.Set("s", salt)
	} else {
		params.Set("p", c.password)
	}
	req.URL.RawQuery = params.Encode()

	fmt.Printf("DO REQ: %+v\n", params)
	fmt.Printf("DO REQ: %+v\n", req)

	resp, err := c.client.Do(req)
	if err != nil {
		c.serverAvailable = false
	}
	return resp, err
}

func (c *Client) getJSON(ctx context.Context, path string, params url.Values) (*Response, error) {
	resp, err := c.get(ctx, path, params)
	if err != nil {
		return nil, err
	}

	// for debugging
	body, _ := io.ReadAll(resp.Body)
	fmt.Printf("%s\n", body)
	resp.Body = io.NopCloser(bytes.NewReader(body))

	var response Response
	if err := json.NewDecoder(resp.Body).Decode(&response); err != nil {
		return nil, err
	}

	if response.SubsonicResponse == nil {
		return nil, ErrNoSubsonicResponse
	}

	if response.SubsonicResponse.Error != nil {
		return nil, response.SubsonicResponse.Error
	}

	c.version = response.SubsonicResponse.Version

	return &response, nil
}
