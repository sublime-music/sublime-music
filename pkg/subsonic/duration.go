package subsonic

import (
	"encoding/json"
	"fmt"
	"time"
)

type SubsonicDuration time.Duration

func (d *SubsonicDuration) UnmarshalJSON(b []byte) error {
	var rawDuration any
	if err := json.Unmarshal(b, &rawDuration); err != nil {
		return err
	}

	switch val := rawDuration.(type) {
	case float64: // All numbers are float64 in JSON
		*d = SubsonicDuration(time.Duration(val) * time.Second)
	default:
		return fmt.Errorf("cannot convert type %T to SubsonicDuration", rawDuration)
	}
	return nil
}

func (d SubsonicDuration) MarshalJSON() ([]byte, error) {
	return json.Marshal(time.Duration(d).String())
}
