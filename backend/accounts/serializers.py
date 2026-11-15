"""
Request/response shapes for /api/auth/ and /api/users/ (docs/openapi.yaml, Auth + Users).

Response serializers are ModelSerializers over USER; request serializers only validate.
Like videos, nothing here saves: views pass validated_data to accounts/services.py.

Field rules (length, characters, reserved nicknames) come from the model's validators, which
ModelSerializer copies. Uniqueness ignoring letter case is checked here (DRF's generated
UniqueValidator is case-sensitive; the DB constraint would otherwise turn a clash into a 500).
"""

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User

MAX_PASSWORD_LENGTH = 128

AVATAR_FORMATS = {'JPEG', 'PNG'}
MAX_AVATAR_SIZE_MB = 5
MAX_AVATAR_SIZE_BYTES = MAX_AVATAR_SIZE_MB * 1024 * 1024


def password_field():
    """A password in a request: never echoed back, no rules (rules run in check_password_rules)."""
    return serializers.CharField(write_only=True, trim_whitespace=False, max_length=MAX_PASSWORD_LENGTH,
                                 style={'input_type': 'password'})


def check_password_rules(password, *, user, field='password'):
    """Django's AUTH_PASSWORD_VALIDATORS (D1.6) as a 400 field error on `field`.

    `user` may be unsaved: the similarity check only needs its username / nickname.
    """
    try:
        password_validation.validate_password(password, user=user)
    except DjangoValidationError as error:
        raise serializers.ValidationError({field: list(error.messages)})


def unique_ignoring_case(field, value, *, exclude=None):
    """Raise if another user already has `value` in `field`, ignoring letter case."""
    users = User.objects.filter(**{f'{field}__iexact': value})
    if exclude is not None:
        users = users.exclude(pk=exclude.pk)
    if users.exists():
        raise serializers.ValidationError(f'A user with that {field} already exists.', code='unique')
    return value


# ---------------------------------------------------------------- responses

class CurrentUserSerializer(serializers.ModelSerializer):
    """CurrentUser: the logged-in user's own data. The only place `username` is ever returned."""

    # Absolute URL when the view passes `request` in the context; null = default avatar.
    avatar_url = serializers.ImageField(source='avatar', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'nickname', 'avatar_url', 'bio']
        read_only_fields = fields


class PublicUserSerializer(serializers.ModelSerializer):
    """PublicUser: what everyone sees. Never `username` (D2.2)."""

    avatar_url = serializers.ImageField(source='avatar', read_only=True)
    public_videos_count = serializers.IntegerField(read_only=True)   # annotated by the view's queryset

    class Meta:
        model = User
        fields = ['nickname', 'avatar_url', 'bio', 'public_videos_count']
        read_only_fields = fields


# ---------------------------------------------------------------- auth requests

class RegisterSerializer(serializers.ModelSerializer):
    """RegisterRequest: username (private), nickname (public), password."""

    password = password_field()

    class Meta:
        model = User
        fields = ['username', 'nickname', 'password']

    def validate_username(self, value):
        return unique_ignoring_case('username', value)

    def validate_nickname(self, value):
        return unique_ignoring_case('nickname', value)

    def validate(self, attrs):
        check_password_rules(attrs['password'], user=User(username=attrs['username'], nickname=attrs['nickname']))
        return attrs


class LoginSerializer(serializers.Serializer):
    """LoginRequest. No rules on purpose (D1.6): wrong values are a 401, not a 400."""

    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, style={'input_type': 'password'})


class PasswordResetSerializer(serializers.Serializer):
    """PasswordResetRequest. new_password rules are checked by the view once the user is known."""

    username = serializers.CharField()
    recovery_code = serializers.CharField()
    new_password = password_field()


# ---------------------------------------------------------------- /api/users/me/ requests

class UpdateProfileSerializer(serializers.ModelSerializer):
    """UpdateProfileRequest (PATCH, multipart or JSON): nickname, bio, avatar. All optional."""

    avatar = serializers.ImageField(required=False, allow_empty_file=False)

    class Meta:
        model = User
        fields = ['nickname', 'bio', 'avatar']

    def validate_nickname(self, value):
        return unique_ignoring_case('nickname', value, exclude=self.instance)

    def validate_avatar(self, file):
        # ImageField has already opened the file with Pillow (a broken or non-image file is a 400 there).
        if file.size > MAX_AVATAR_SIZE_BYTES:
            raise serializers.ValidationError(f'Avatar is too large (max {MAX_AVATAR_SIZE_MB} MB).')
        if getattr(file, 'image', None) is None or file.image.format not in AVATAR_FORMATS:
            raise serializers.ValidationError('Avatar must be a JPEG or PNG image.')
        return file


class UpdateUsernameSerializer(serializers.ModelSerializer):
    """UpdateUsernameRequest: the new username + the current password as a confirmation."""

    password = password_field()

    class Meta:
        model = User
        fields = ['username', 'password']

    def validate_username(self, value):
        return unique_ignoring_case('username', value, exclude=self.instance)


class ChangePasswordSerializer(serializers.Serializer):
    """ChangePasswordRequest. The view passes the user in the context for the similarity rule."""

    old_password = password_field()
    new_password = password_field()

    def validate(self, attrs):
        check_password_rules(attrs['new_password'], user=self.context['user'], field='new_password')
        return attrs


class PasswordConfirmSerializer(serializers.Serializer):
    """PasswordConfirmRequest: the current password (account delete, new recovery code)."""

    password = password_field()
