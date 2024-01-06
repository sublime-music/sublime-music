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

	ErrGeneric                              = &SubsonicError{Code: 0, Message: "generic error"}
	ErrParameterMissing                     = &SubsonicError{Code: 10, Message: "required parameter is missing"}
	ErrIncompatibleVersionClientMustUpgrade = &SubsonicError{Code: 20, Message: "client is too old. server requires newer protocol version"}
	ErrIncompatibleVersionServerMustUpgrade = &SubsonicError{Code: 30, Message: "server is too old. client requires newer protocol version"}
	ErrWrongUsernameOrPassword              = &SubsonicError{Code: 40, Message: "wrong username or password"}
	ErrTokenAuthenticationNotSupported      = &SubsonicError{Code: 41, Message: "token-based authentication not supported for LDAP users"}
	ErrUserNotAuthorized                    = &SubsonicError{Code: 50, Message: "user is not authorized for the given operation"}
	ErrTrialPeriodExpired                   = &SubsonicError{Code: 60, Message: "trial period expired"}
	ErrDataNotFound                         = &SubsonicError{Code: 70, Message: "requested data was not found"}
)
