package subsonic_test

import (
	"context"
	"encoding/json"
	"fmt"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/sublime-music/sublime-music/pkg/subsonic"
)

func TestPing(t *testing.T) {
	client, err := subsonic.NewClient("https://music.sumnerevans.com", "sumner", "uyZ5MquH2rWspiawtabazbmpE", true, true)
	assert.NoError(t, err)

	pingResp, err := client.Ping(context.TODO())
	assert.NoError(t, err)
	fmt.Printf("%+v\n", pingResp)

	license, err := client.GetArtists(context.TODO(), nil)
	assert.NoError(t, err)
	ohea, _ := json.Marshal(license)
	fmt.Printf("%s\n", ohea)
	panic("stop")
}
