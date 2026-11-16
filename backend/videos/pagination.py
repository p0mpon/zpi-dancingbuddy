"""Pagination of the video lists (docs/api-decisions.md D7.3)."""

from rest_framework.pagination import LimitOffsetPagination


class VideoPagination(LimitOffsetPagination):
    """?limit=&offset= -> {count, next, previous, results}.

    The default page size (20) comes from PAGE_SIZE in settings. The only thing added here is the
    cap: `?limit=5000` is quietly treated as `?limit=100`, so one request can't pull the whole table.
    """

    max_limit = 100
