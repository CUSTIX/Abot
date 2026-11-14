from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api import OwnedViewSet
from utang import selectors, services
from utang.models import UtangPayment
from utang.serializers import AddPaymentSerializer, UtangSerializer, UtangUpdateSerializer


class UtangViewSet(OwnedViewSet):
    serializer_class = UtangSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete"]

    def queryset_for(self, user):
        return selectors.with_totals(user)

    def _fresh(self, pk):
        return selectors.with_totals(self.request.user).get(pk=pk)

    def create(self, request, *args, **kwargs):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        utang = services.create(owner=request.user, **data.validated_data)
        return Response(self.get_serializer(self._fresh(utang.pk)).data, status=201)

    def partial_update(self, request, *args, **kwargs):
        utang = self.get_object()
        data = UtangUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.update(utang, **data.validated_data)
        return Response(self.get_serializer(self._fresh(utang.pk)).data)

    def perform_destroy(self, instance):
        services.delete(instance)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        utang = self.get_object()
        data = AddPaymentSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        services.add_payment(
            utang,
            amount=data.validated_data["amount"],
            date=data.validated_data.get("date") or timezone.localdate(),
            wallet=data.validated_data.get("wallet"),
        )
        return Response(self.get_serializer(self._fresh(utang.pk)).data, status=201)

    @action(detail=True, methods=["delete"], url_path=r"payments/(?P<payment_id>\d+)")
    def remove_payment(self, request, pk=None, payment_id=None):
        utang = self.get_object()
        services.delete_payment(get_object_or_404(UtangPayment, utang=utang, pk=payment_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class UtangSummaryView(APIView):
    def get(self, request):
        totals = selectors.summary(request.user)
        return Response({k: str(v.quantize(Decimal("0.01"))) for k, v in totals.items()})
