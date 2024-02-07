package subsonic

import (
	"encoding/json"
	"errors"
	"net/url"
	"reflect"
	"strings"
	"time"
)

func toString(val any) (string, error) {
	jsonVal, err := json.Marshal(val)
	if err != nil {
		return "", err
	}

	// It was a string, remove the quotes.
	if jsonVal[0] == '"' && jsonVal[len(jsonVal)-1] == '"' {
		jsonVal = jsonVal[1 : len(jsonVal)-1]
	}
	return string(jsonVal), nil
}

// MarshalValues converts a struct to a [url.Values]. It uses the "url" tag to
// determine the name of the field in the resulting [url.Values]. If the "url"
// tag is not present, it uses the field name. If the "omitempty" option is
// present, it will not include the field in the resulting [url.Values] if the
// field is empty.
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

		fieldVal := reflect.ValueOf(in).Field(i)

		if field.Type.Kind() == reflect.Slice {
			if omitEmpty && fieldVal.Len() == 0 {
				continue
			}
			var vals []string
			for i := 0; i < fieldVal.Len(); i++ {
				val := fieldVal.Index(i).Interface()
				jsonVal, err := toString(val)
				if err != nil {
					return nil, err
				}
				vals = append(vals, jsonVal)
			}
			out[name] = vals
			continue
		}
		val := fieldVal.Interface()
		switch vt := fieldVal.Interface().(type) {
		case time.Time:
			if omitEmpty && vt.UnixNano() == 0 {
				continue
			}
			val = vt.Format(time.RFC3339)
		case *time.Time:
			if vt != nil {
				if omitEmpty && vt.IsZero() {
					continue
				}
				val = vt.Format(time.RFC3339)
			}
		case int, int16, int32, int64, float32, float64:
			if omitEmpty && vt == 0 {
				continue
			}
		case bool:
			if omitEmpty && !vt {
				continue
			}
		}

		jsonVal, err := toString(val)
		if err != nil {
			return nil, err
		}

		if omitEmpty {
			if jsonVal == "null" {
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
