package subsonic

import (
	"bytes"
	"encoding/json"
	"errors"
	"net/url"
	"reflect"
	"strings"
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

		v, err := json.Marshal(reflect.ValueOf(in).Field(i).Interface())
		if err != nil {
			return nil, err
		}

		// It was a string, remove the quotes.
		if v[0] == '"' && v[len(v)-1] == '"' {
			v = v[1 : len(v)-1]
		}

		if omitEmpty {
			if bytes.Equal(v, []byte("null")) {
				continue
			}

			if len(v) == 0 {
				continue
			}
		}

		out[name] = []string{string(v)}
	}
	return out, nil
}
