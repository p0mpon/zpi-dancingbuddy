"""
Auth and users API (docs/openapi.yaml, Auth + Users). Routes (registered in zpi_app/urls.py):

    GET     /api/auth/csrf/                 CsrfView            sets the csrftoken cookie
    POST    /api/auth/register/             RegisterView        201 CurrentUser + recovery_code, logged in
    POST    /api/auth/login/                LoginView           200 CurrentUser
    POST    /api/auth/logout/               LogoutView          204
    POST    /api/auth/password-reset/       PasswordResetView   200 {recovery_code}

    GET     /api/users/me/                  UserViewSet.me
    PATCH   /api/users/me/                  UserViewSet.update_me      (nickname, bio, avatar)
    DELETE  /api/users/me/                  UserViewSet.delete_me      (password in the body)
    PATCH   /api/users/me/username/         UserViewSet.change_username
    POST    /api/users/me/password/         UserViewSet.change_password
    POST    /api/users/me/recovery-code/    UserViewSet.recovery_code
    DELETE  /api/users/me/avatar/           UserViewSet.delete_avatar
    GET     /api/users/{nickname}/          UserViewSet.retrieve       public profile

Views only deal with HTTP: validate with a serializer, call accounts/services.py for writes,
log in / out with Django's auth functions, return a response.

Status codes: not logged in and wrong login -> 401 (accounts.authentication), wrong password
confirmation -> 403, validation -> 400 (D7.5).
"""

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from videos.models import Visibility

from . import services
from .models import User
from .serializers import (
    ChangePasswordSerializer,
    CurrentUserSerializer,
    LoginSerializer,
    PasswordConfirmSerializer,
    PasswordResetSerializer,
    PublicUserSerializer,
    RegisterSerializer,
    UpdateProfileSerializer,
    UpdateUsernameSerializer,
    check_password_rules,
)
from .services import InvalidRecoveryCode, WrongPassword
from .throttling import IPScopedRateThrottle


def current_user(request, user=None, status_code=status.HTTP_200_OK, **extra):
    """A CurrentUser response (absolute avatar_url needs the request), plus any extra keys."""
    data = CurrentUserSerializer(user or request.user, context={'request': request}).data
    return Response({**data, **extra}, status=status_code)


# ---------------------------------------------------------------- /api/auth/

# DRF exempts its views from Django's CSRF check and checks CSRF itself only for logged-in users.
# Register, login and password reset are used while logged out, so csrf_protect turns the check
# back on: the spec requires X-CSRFToken on them (D1.4), which also stops login CSRF.
anonymous_csrf = method_decorator(csrf_protect, name='dispatch')


class CsrfView(APIView):
    permission_classes = [AllowAny]

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@anonymous_csrf
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [IPScopedRateThrottle]
    throttle_scope = 'register'

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, recovery_code = services.register_user(**serializer.validated_data)
        login(request, user)    # D1.5: registered = logged in
        return current_user(request, user, status.HTTP_201_CREATED, recovery_code=recovery_code)


@anonymous_csrf
class LoginView(APIView):
    # Keeps the default authentication classes: their WWW-Authenticate header is what makes
    # AuthenticationFailed a 401 here (with none, DRF answers 403).
    permission_classes = [AllowAny]
    throttle_classes = [IPScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # ModelBackend: matches the username ignoring case and refuses inactive users.
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            raise AuthenticationFailed('Invalid username or password.')
        login(request, user)    # also rotates the CSRF token: the frontend must re-read the cookie
        return current_user(request, user)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@anonymous_csrf
class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [IPScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = services.user_for_recovery(username=data['username'], recovery_code=data['recovery_code'])
        except InvalidRecoveryCode as error:
            return Response({'detail': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        # Checked only now: the similarity rule needs the user, and a code check must come first
        # so password rules don't hint whether the username exists.
        check_password_rules(data['new_password'], user=user, field='new_password')
        recovery_code = services.reset_password(user=user, new_password=data['new_password'])
        return Response({'recovery_code': recovery_code})


# ---------------------------------------------------------------- /api/users/

class UserViewSet(viewsets.GenericViewSet):
    # Blocked users (is_active = false) don't exist for the public profile (404).
    queryset = User.objects.filter(is_active=True).annotate(
        public_videos_count=Count('videos', filter=Q(videos__visibility=Visibility.PUBLIC)),
    )
    serializer_class = PublicUserSerializer
    lookup_field = 'nickname'
    lookup_value_regex = r'[A-Za-z0-9_.-]+'      # the nickname's characters; `me` is reserved, so no clash
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_object(self):
        # Nicknames are unique ignoring case, so /users/ANA/ finds `Ana` too.
        return get_object_or_404(self.get_queryset(), nickname__iexact=self.kwargs['nickname'])

    def retrieve(self, request, nickname=None):
        return Response(self.get_serializer(self.get_object()).data)

    # ---- /api/users/me/

    @action(detail=False, methods=['get'])
    def me(self, request):
        return current_user(request)

    @me.mapping.patch
    def update_me(self, request):
        serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = services.update_profile(user=request.user, **serializer.validated_data)
        return current_user(request, user)

    @me.mapping.delete
    def delete_me(self, request):
        serializer = PasswordConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.delete_account(user=request.user, **serializer.validated_data)
        except WrongPassword as error:
            raise PermissionDenied(str(error))   # 403: wrong password confirmation
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['patch'], url_path='me/username')
    def change_username(self, request):
        serializer = UpdateUsernameSerializer(request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = services.change_username(user=request.user, **serializer.validated_data)
        except WrongPassword as error:
            raise PermissionDenied(str(error))   # 403: wrong password confirmation
        return current_user(request, user)

    @action(detail=False, methods=['post'], url_path='me/password')
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'user': request.user})
        serializer.is_valid(raise_exception=True)
        try:
            user = services.change_password(user=request.user, **serializer.validated_data)
        except WrongPassword as error:
            raise PermissionDenied(str(error))   # 403: wrong password confirmation
        update_session_auth_hash(request, user)     # keep this session; the others are logged out
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='me/recovery-code')
    def recovery_code(self, request):
        serializer = PasswordConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            code = services.regenerate_recovery_code(user=request.user, **serializer.validated_data)
        except WrongPassword as error:
            raise PermissionDenied(str(error))   # 403: wrong password confirmation
        return Response({'recovery_code': code})

    @action(detail=False, methods=['delete'], url_path='me/avatar')
    def delete_avatar(self, request):
        services.remove_avatar(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
