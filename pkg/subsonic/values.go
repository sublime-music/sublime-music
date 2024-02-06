package subsonic

import (
	"bytes"
	"encoding/json"
	"errors"
	"net/url"
	"reflect"
	"strings"
	"time"
)

func MarshalValues(in any) (url.Values, error) {
	out := url.Values{}
	st := reflect.TypeOf(in)
	for i := 0; i < st.NumField(); i++ {
		field := st.Field(i)
		name, ok := field.Tag.Lookup("url")
		var omitEmpty bool
		if ok {
			nameParts := strings.Split(name, ",")
			name = nameParts[0]
			for _, part := range nameParts[1:] {
				if part == "omitempty" {
					omitEmpty = true
				}
			}
		} else {
			name = field.Name
		}
		if name == "" {
			return nil, errors.New("invalid 'url' tag")
		}

		val := reflect.ValueOf(in).Field(i).Interface()
		switch vt := val.(type) {
		case time.Time:
			val = vt.Format(time.RFC3339)
		case *time.Time:
			if vt != nil {
				val = vt.Format(time.RFC3339)
			}
		}

		jsonVal, err := json.Marshal(val)
		if err != nil {
			return nil, err
		}

		// It was a string, remove the quotes.
		if jsonVal[0] == '"' && jsonVal[len(jsonVal)-1] == '"' {
			jsonVal = jsonVal[1 : len(jsonVal)-1]
		}

		if omitEmpty {
			if bytes.Equal(jsonVal, []byte("null")) {
				continue
			}

			if len(jsonVal) == 0 {
				continue
			}
		}

		out[name] = []string{string(jsonVal)}
	}
	return out, nil
}
