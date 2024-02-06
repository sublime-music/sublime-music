package subsonic_test

import (
	"encoding/json"
	"fmt"
	"net/url"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/sublime-music/sublime-music/pkg/subsonic"
)

type Complex string

func (c Complex) MarshalJSON() ([]byte, error) {
	return json.Marshal(fmt.Sprintf(`aaaaa %s bbbbb`, c))
}

type Foo struct {
	A string `url:"a"`
	B int
	C Complex    `url:"c,omitempty"`
	D string     `url:"d,omitempty"`
	E *int       `url:"e,omitempty"`
	F time.Time  `url:"f,omitempty"`
	G *time.Time `url:"g,omitempty"`
	H []string   `url:"h,omitempty"`
	I []Complex  `url:"i,omitempty"`
}

func TestMarshalValues(t *testing.T) {
	values, err := subsonic.MarshalValues(Foo{
		A: "test",
		B: 4,
		C: "bar",
		F: time.UnixMilli(1707175937000),
		H: []string{"a", "b", "c"},
		I: []Complex{"foo", "bar"},
	})
	require.NoError(t, err)
	assert.Equal(t, url.Values{
		"a": []string{"test"},
		"B": []string{"4"},
		"c": []string{"aaaaa bar bbbbb"},
		"f": []string{"2024-02-05T16:32:17-07:00"},
		"h": []string{"a", "b", "c"},
		"i": []string{"aaaaa foo bbbbb", "aaaaa bar bbbbb"},
	}, values)
}

func FuzzMarshalValues(f *testing.F) {
	f.Add("test", 4, "bar", "", -1, int64(0), int64(0))
	f.Add("test", 20, "baz", "present", 1, int64(0), int64(0))

	f.Fuzz(func(t *testing.T, a string, b int, c string, d string, e int, f, g int64) {
		var eVal *int
		if e >= 0 {
			eVal = &e
		}
		var gVal *time.Time
		if g > 0 {
			t := time.UnixMilli(g)
			gVal = &t
		}
		values, err := subsonic.MarshalValues(Foo{
			A: a,
			B: b,
			C: Complex(c),
			D: d,
			E: eVal,
			F: time.UnixMilli(f),
			G: gVal,
		})
		require.NoError(t, err)

		assert.Contains(t, values, "a")
		assert.Contains(t, values, "B")
		assert.Contains(t, values, "c")
		if d != "" {
			assert.Contains(t, values, "d")
		}
		if e >= 0 {
			assert.Contains(t, values, "e")
		}
		if f == 0 {
			assert.Contains(t, values, "f")
		}
		if g > 0 {
			assert.Contains(t, values, "g")
		}
	})
}
