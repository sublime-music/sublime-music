package subsonic

import "fmt"

// Error is an error coming from the Subsonic server.
//
// Docs: [OpenSubsonic]
//
// Subsonic 1.16.1 Definition:
//
//	<xs:complexType name="Error">
//	    <xs:attribute name="code" type="xs:int" use="required"/>
//	    <xs:attribute name="message" type="xs:string" use="optional"/>
//	</xs:complexType>
//
// [OpenSubsonic] https://opensubsonic.netlify.app/docs/responses/error/
type Error struct {
	Code    int    `json:"code"`
	Message string `json:"message,omitempty"`
}

func (e *Error) Error() string {
	if e.Message == "" {
		return fmt.Sprintf("Error(%d)", e.Code)
	}
	return fmt.Sprintf("Error(%d: %s)", e.Code, e.Message)
}

func (e *Error) Is(err error) bool {
	e2, ok := err.(*Error)
	return ok && e.Code == e2.Code
}

var (
	ErrNoSubsonicResponse               = &Error{Code: -1, Message: "server returned invalid JSON"}
	ErrServerDoesNotSupportOpenSubsonic = &Error{Code: -2, Message: "server does not support OpenSubsonic"}

	ErrGeneric                              = &Error{Code: 0, Message: "generic error"}
	ErrParameterMissing                     = &Error{Code: 10, Message: "required parameter is missing"}
	ErrIncompatibleVersionClientMustUpgrade = &Error{Code: 20, Message: "client is too old. server requires newer protocol version"}
	ErrIncompatibleVersionServerMustUpgrade = &Error{Code: 30, Message: "server is too old. client requires newer protocol version"}
	ErrWrongUsernameOrPassword              = &Error{Code: 40, Message: "wrong username or password"}
	ErrTokenAuthenticationNotSupported      = &Error{Code: 41, Message: "token-based authentication not supported for LDAP users"}
	ErrUserNotAuthorized                    = &Error{Code: 50, Message: "user is not authorized for the given operation"}
	ErrTrialPeriodExpired                   = &Error{Code: 60, Message: "trial period expired"}
	ErrDataNotFound                         = &Error{Code: 70, Message: "requested data was not found"}
)
