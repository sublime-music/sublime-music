package subsonic

import (
	"encoding/json"
	"fmt"
)

type SubsonicID string

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

func (id SubsonicID) String() string {
	return string(id)
}

func idsToStrings(ids []SubsonicID) (strs []string) {
	for i, id := range ids {
		strs[i] = id.String()
	}
	return
}
