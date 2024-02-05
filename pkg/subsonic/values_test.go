package subsonic_test

import (
	"encoding/json"
	"fmt"
	"net/url"
	"testing"

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
	C Complex `url:"c,omitempty"`
	D string  `url:"d,omitempty"`
	E *int    `url:"e,omitempty"`
}

func TestMarshalValues(t *testing.T) {
	values, err := subsonic.MarshalValues(Foo{
		A: "test",
		B: 4,
		C: "bar",
	})
	require.NoError(t, err)
	assert.Equal(t, url.Values{
		"a": []string{"test"},
		"B": []string{"4"},
		"c": []string{"aaaaa bar bbbbb"},
	}, values)
}

func FuzzMarshalValues(f *testing.F) {
	f.Add("test", 4, "bar", "", -1)
	f.Add("test", 20, "baz", "present", 1)

	f.Fuzz(func(t *testing.T, a string, b int, c string, d string, e int) {
		var eVal *int
		if e >= 0 {
			eVal = &e
		}
		values, err := subsonic.MarshalValues(Foo{
			A: a,
			B: b,
			C: Complex(c),
			D: d,
			E: eVal,
		})
		require.NoError(t, err)

		assert.Contains(t, values, "a")
		assert.Contains(t, values, "B")
		assert.Contains(t, values, "c")
	})
}
