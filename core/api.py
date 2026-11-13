"""Small helpers shared by the API views."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, viewsets
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """Services raise Django's ValidationError; answer it like a serializer error (400 + fields)."""
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "error_dict") else {"detail": exc.messages}
        exc = serializers.ValidationError(detail)
    return drf_exception_handler(exc, context)


class OwnedPrimaryKeyField(serializers.PrimaryKeyRelatedField):
    """Only accepts ids of the signed-in user's own rows; anyone else's id is "does not exist"."""

    def get_queryset(self):
        return self.queryset.model.objects.filter(owner=self.context["request"].user)


class OwnedViewSet(viewsets.ModelViewSet):
    """CRUD on the signed-in user's own rows only. Another user's id is a 404 (not 403), so ids
    can't be probed. Subclasses implement `queryset_for(user)`."""

    def queryset_for(self, user):  # pragma: no cover - overridden
        raise NotImplementedError

    def get_queryset(self):
        return self.queryset_for(self.request.user)
