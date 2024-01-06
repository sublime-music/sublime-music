package subsonic

import (
	"encoding/json"
	"fmt"
)

// SubsonicID is an ID from a Subsonic server. It is always stored as a string,
// but can be specified as either a string or a number in the JSON.
type SubsonicID string

// UnmarshalJSON implements the [json.Unmarshaler] interface for [SubsonicID].
func (id *SubsonicID) UnmarshalJSON(b []byte) error {
	var rawID any
	if err := json.Unmarshal(b, &rawID); err != nil {
		return err
	}

	switch val := rawID.(type) {
	case string:
		*id = SubsonicID(val)
	case float64: // All numbers are float64 in JSON
		*id = SubsonicID(fmt.Sprintf("%d", int(val)))
	default:
		return fmt.Errorf("cannot convert type %T to Subsonic ID", rawID)
	}
	return nil
}

// String gets the underlying string of the [SubsonicID].
func (id SubsonicID) String() string {
	return string(id)
}

func idsToStrings(ids []SubsonicID) (strs []string) {
	for i, id := range ids {
		strs[i] = id.String()
	}
	return
}
