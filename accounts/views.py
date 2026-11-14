from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import services
from accounts.serializers import LoginSerializer, MeSerializer, SignUpSerializer
from core.throttles import ClientIPScopedThrottle


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """The SPA asks for a CSRF token once and sends it as X-CSRFToken on every write. The cookie
    is HttpOnly, so the token is handed over in the body instead."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        demo = (
            {"username": settings.DEMO_USERNAME, "password": settings.DEMO_PASSWORD}
            if settings.DEMO_MODE
            else None
        )
        return Response({"csrfToken": get_token(request), "demo": demo})


# DRF skips CSRF for anonymous requests; login/sign-up need it anyway (login CSRF: an attacker
# could otherwise sign a victim into the attacker's account).
@method_decorator(csrf_protect, name="dispatch")
class SignUpView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ClientIPScopedThrottle]
    throttle_scope = "signup"

    def post(self, request):
        data = SignUpSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            user = services.sign_up(**data.validated_data)
        except DjangoValidationError as exc:
            return Response({"password": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response(MeSerializer(user).data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ClientIPScopedThrottle]
    throttle_scope = "login"

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = authenticate(request, **data.validated_data)
        if user is None:
            return Response(
                {"detail": "Wrong username or password."}, status=status.HTTP_400_BAD_REQUEST
            )
        login(request, user)
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """{"user": ...} or {"user": null}: the app can ask without causing a console error."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"user": None})
        return Response({"user": MeSerializer(request.user).data})
