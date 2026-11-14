from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.api import OwnedViewSet
from paluwagan import selectors, services
from paluwagan.models import Paluwagan, PaluwaganEntry
from paluwagan.serializers import PaluwaganSerializer, RecordSerializer


class PaluwaganViewSet(OwnedViewSet):
    serializer_class = PaluwaganSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete"]

    def queryset_for(self, user):
        return selectors.for_owner(user)

    def get_serializer_context(self):
        # One pay-schedule lookup for the whole list, not one per paluwagan.
        return {
            **super().get_serializer_context(),
            "schedule": selectors.pay_schedule(self.request.user),
        }

    def perform_create(self, serializer):
        serializer.instance = services.save(
            Paluwagan(owner=self.request.user, **serializer.validated_data)
        )

    def perform_update(self, serializer):
        p = serializer.instance
        for name, value in serializer.validated_data.items():
            setattr(p, name, value)
        services.save(p)

    def perform_destroy(self, instance):
        services.delete(instance)

    def _fresh(self, pk):
        return self.get_serializer(selectors.for_owner(self.request.user).get(pk=pk)).data

    @action(detail=True, methods=["post"])
    def record(self, request, pk=None):
        p = self.get_object()
        data = RecordSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        services.record(
            p,
            kind=data.validated_data["kind"],
            round_number=data.validated_data["round"],
            date=data.validated_data.get("date") or timezone.localdate(),
            wallet=data.validated_data.get("wallet"),
        )
        return Response(self._fresh(p.pk), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"entries/(?P<entry_id>\d+)")
    def undo(self, request, pk=None, entry_id=None):
        p = self.get_object()
        services.undo(get_object_or_404(PaluwaganEntry, paluwagan=p, pk=entry_id))
        return Response(status=status.HTTP_204_NO_CONTENT)
