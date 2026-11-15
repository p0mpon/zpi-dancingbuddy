from rest_framework.throttling import ScopedRateThrottle


class IPScopedRateThrottle(ScopedRateThrottle):
    """ScopedRateThrottle that always counts per client IP (D1.2), even for logged-in requests.

    DRF's version counts per user once someone is logged in. Register logs the new user in, so
    each new account would start a fresh counter, and a logged-in attacker could guess other
    accounts' passwords on their own counter. The IP comes from REMOTE_ADDR, or from
    X-Forwarded-For when REST_FRAMEWORK['NUM_PROXIES'] is set.
    """

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}
