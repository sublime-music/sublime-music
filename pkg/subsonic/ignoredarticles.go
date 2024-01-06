package subsonic

import (
	"encoding/json"
	"strings"
)

// IgnoredArticles is a list of articles that are ignored when sorting an
// index.
type IgnoredArticles []string

// UnmarshalJSON implements the [json.Unmarshaler] interface. It takes the
// space-separated articles and splits them into a slice.
func (a *IgnoredArticles) UnmarshalJSON(b []byte) error {
	var rawArticles string
	if err := json.Unmarshal(b, &rawArticles); err != nil {
		return err
	}

	if rawArticles == "" {
		*a = nil
	} else {
		*a = strings.Split(rawArticles, " ")
	}
	return nil
}

// MarshalJSON implements the [json.Marshaler] interface. It combines the
// ignored articles together into a space-separated string.
func (a IgnoredArticles) MarshalJSON() ([]byte, error) {
	return json.Marshal(strings.Join(a, " "))
}
