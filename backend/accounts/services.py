"""
Every write to USER goes through here (like videos/services.py). Views only deal with HTTP.

Passwords and the recovery code are hashed by Django (make_password / set_password); there is
no hash function of our own. Changing the password changes the session hash, so Django logs out
the user's other sessions by itself on their next request (the view keeps the current one alive
with update_session_auth_hash where the spec asks for it).

Files: deleting a user removes the avatar through a post_delete signal (accounts/signals.py), and
CASCADE removes their videos / attempts files through the signals in those apps.
"""

import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction

from .models import User

RECOVERY_CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'   # no 0/O, 1/I/L: easy to copy by hand
RECOVERY_CODE_LENGTH = 16                                    # 31^16 ≈ 2^79
RECOVERY_CODE_GROUP = 4                                      # shown as XXXX-XXXX-XXXX-XXXX


class AccountServiceError(Exception):
    """Base class for errors the views turn into a response."""


class WrongPassword(AccountServiceError):
    """The password confirmation is wrong (403 in the spec)."""


class InvalidRecoveryCode(AccountServiceError):
    """Wrong username or wrong code: one error for both, so it doesn't reveal which usernames exist."""


# ---------------------------------------------------------------- recovery code (D1.7)

def _new_recovery_code():
    raw = ''.join(secrets.choice(RECOVERY_CODE_ALPHABET) for _ in range(RECOVERY_CODE_LENGTH))
    return '-'.join(raw[i:i + RECOVERY_CODE_GROUP] for i in range(0, RECOVERY_CODE_LENGTH, RECOVERY_CODE_GROUP))


def _normalize_recovery_code(code):
    """The user may type it with or without dashes / spaces, in any letter case."""
    return code.replace('-', '').replace(' ', '').upper()


def _set_new_recovery_code(user):
    """Replace the user's code (unsaved); return the plain code, which is never stored."""
    code = _new_recovery_code()
    user.recovery_code_hash = make_password(_normalize_recovery_code(code))
    return code


def user_for_recovery(*, username, recovery_code):
    """The active user whose username and recovery code match, else InvalidRecoveryCode."""
    user = User.objects.filter(username__iexact=username, is_active=True).first()
    if user is None or not user.recovery_code_hash:
        make_password(recovery_code)    # same hashing time as a real check, so timing doesn't reveal the username
        raise InvalidRecoveryCode('Invalid username or recovery code.')
    if not check_password(_normalize_recovery_code(recovery_code), user.recovery_code_hash):
        raise InvalidRecoveryCode('Invalid username or recovery code.')
    return user


def reset_password(*, user, new_password):
    """Set a new password with the recovery code (already checked by user_for_recovery).

    The used code stops working and a new one is returned (show it once). The password hash
    changes, so all the user's sessions are logged out.
    """
    user.set_password(new_password)
    code = _set_new_recovery_code(user)
    user.save(update_fields=['password', 'recovery_code_hash'])
    return code


def regenerate_recovery_code(*, user, password):
    """POST /api/users/me/recovery-code/: a new code for a logged-in user (the old one stops working)."""
    confirm_password(user=user, password=password)
    code = _set_new_recovery_code(user)
    user.save(update_fields=['recovery_code_hash'])
    return code


# ---------------------------------------------------------------- register / account

def register_user(*, username, nickname, password):
    """Create the account and its first recovery code. Returns (user, plain recovery code)."""
    user = User(username=username, nickname=nickname)
    user.set_password(password)
    code = _set_new_recovery_code(user)
    user.save()
    return user, code


def confirm_password(*, user, password):
    if not user.check_password(password):
        raise WrongPassword('Password is incorrect.')


def change_username(*, user, username, password):
    """Change the private sign-in name. The session stays valid (it doesn't depend on the username)."""
    confirm_password(user=user, password=password)
    user.username = username
    user.save(update_fields=['username'])
    return user


def change_password(*, user, old_password, new_password):
    """Change the password; other sessions are logged out (the view keeps the current one)."""
    confirm_password(user=user, password=old_password)
    user.set_password(new_password)
    user.save(update_fields=['password'])
    return user


def delete_account(*, user, password):
    """Delete the user and, by CASCADE, their videos, likes and attempts (files via post_delete signals)."""
    confirm_password(user=user, password=password)
    user.delete()


# ---------------------------------------------------------------- profile

def _delete_file_after_commit(field_file):
    """Remove a stored file once the transaction commits (if it rolls back, the row still points to it)."""
    if field_file:
        storage, name = field_file.storage, field_file.name
        transaction.on_commit(lambda: storage.delete(name))


def update_profile(*, user, **fields):
    """PATCH /api/users/me/: nickname, bio and / or avatar. Nothing sent = nothing changes.

    A new avatar replaces the old one; the old file is deleted after the commit.
    The avatar arrives already processed (512x512 WebP, core.images via UpdateProfileSerializer).
    """
    if not fields:
        return user
    with transaction.atomic():
        if 'avatar' in fields:
            _delete_file_after_commit(user.avatar)
        for name, value in fields.items():
            setattr(user, name, value)
        user.save(update_fields=list(fields))   # saving `avatar` writes the new file to storage
    return user


def remove_avatar(*, user):
    """DELETE /api/users/me/avatar/: back to the default avatar. No avatar = nothing to do."""
    if not user.avatar:
        return user
    with transaction.atomic():
        _delete_file_after_commit(user.avatar)
        user.avatar = None
        user.save(update_fields=['avatar'])
    return user
