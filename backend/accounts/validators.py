"""
Field rules for USER (db/diagram/v2.md, docs/api-decisions.md D1.1, D2.1, D2.3).

Model validators run in full_clean() (admin forms) and are copied by DRF's ModelSerializer,
so the API checks the same rules without declaring them again.
"""

from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, RegexValidator

USERNAME_MIN_LENGTH = 6
USERNAME_MAX_LENGTH = 32

NICKNAME_MIN_LENGTH = 3
NICKNAME_MAX_LENGTH = 32

# `me` clashes with /api/users/me/ next to /api/users/{nickname}/ (D2.3); the rest prevent impersonation.
# Migration 0003_user_fields has a frozen copy of this list: adding names here doesn't need a new migration.
RESERVED_NICKNAMES = frozenset({
    'me', 'admin', 'administrator', 'root', 'system', 'staff', 'support',
    'moderator', 'mod', 'help', 'api', 'null', 'undefined', 'onbeat', 'dancingbuddy',
})

username_min_length = MinLengthValidator(USERNAME_MIN_LENGTH)
nickname_min_length = MinLengthValidator(NICKNAME_MIN_LENGTH)

# The nickname is part of URLs (/api/users/{nickname}/, ?author=), so only URL-safe characters.
nickname_characters = RegexValidator(
    regex=r'^[A-Za-z0-9_.-]+\Z',
    message='Nickname may contain only letters, digits and . _ - characters.',
    code='invalid_nickname',
)


def validate_nickname_not_reserved(value):
    """Reject reserved nicknames (case-insensitive: `Me`, `ADMIN` too)."""
    if value.lower() in RESERVED_NICKNAMES:
        raise ValidationError('This nickname is reserved.', code='reserved_nickname')
