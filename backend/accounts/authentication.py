from rest_framework import authentication


class SessionAuthentication(authentication.SessionAuthentication):
    """DRF's session auth, but "not logged in" is 401 instead of 403 (docs/api-decisions.md D7.5).

    DRF turns NotAuthenticated / AuthenticationFailed into 401 only if the first authentication
    class returns a WWW-Authenticate value; the stock SessionAuthentication returns none, so DRF
    falls back to 403. That would also mix "not logged in" with "wrong password" (403 in the spec).
    `Session` is not a scheme browsers know, so no login popup appears (unlike `Basic`).
    """

    def authenticate_header(self, request):
        return 'Session'
