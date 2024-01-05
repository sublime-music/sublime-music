package subsonic

import (
	"encoding/json"
	"strings"
)

type IgnoredArticles []string

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
