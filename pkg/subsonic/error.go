package subsonic

import "fmt"

type SubsonicError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

func (e *SubsonicError) Error() string {
	return fmt.Sprintf("SubsonicError(%d: %s)", e.Code, e.Message)
}

func (e *SubsonicError) Is(err error) bool {
	e2, ok := err.(*SubsonicError)
	return ok && e.Code == e2.Code
}

var (
	ErrNoSubsonicResponse               = &SubsonicError{Code: -1, Message: "server returned invalid JSON"}
	ErrServerDoesNotSupportOpenSubsonic = &SubsonicError{Code: -2, Message: "server does not support OpenSubsonic"}
)
