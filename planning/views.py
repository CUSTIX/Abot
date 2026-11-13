from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api import OwnedViewSet
from money.serializers import TransactionSerializer
from planning import selectors, services
from planning.models import Bill, BillPayment, SplitRule
from planning.serializers import (
    BillSerializer,
    PayBillSerializer,
    ReceivePaySerializer,
    ScheduleSerializer,
    SplitRuleSerializer,
    today_payload,
)


class TodayView(APIView):
    """The home screen: safe to spend today, this cycle's bills, spending, recent activity."""

    def get(self, request):
        data = selectors.today(request.user, timezone.localdate())
        return Response(today_payload(data, {"request": request}))


class ScheduleView(APIView):
    def get(self, request):
        return Response(ScheduleSerializer(services.schedule_for(request.user)).data)

    def put(self, request):
        schedule = services.schedule_for(request.user)
        data = ScheduleSerializer(schedule, data=request.data)
        data.is_valid(raise_exception=True)
        for name, value in data.validated_data.items():
            setattr(schedule, name, value)
        services.save_schedule(schedule)
        return Response(ScheduleSerializer(schedule).data)


class BillViewSet(OwnedViewSet):
    serializer_class = BillSerializer
    pagination_class = None

    def queryset_for(self, user):
        return selectors.bills(user)

    def perform_create(self, serializer):
        serializer.instance = services.save_bill(
            Bill(owner=self.request.user, **serializer.validated_data)
        )

    def perform_update(self, serializer):
        bill = serializer.instance
        for name, value in serializer.validated_data.items():
            setattr(bill, name, value)
        services.save_bill(bill)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        bill = self.get_object()
        data = PayBillSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        payment = services.pay_bill(
            bill,
            due_date=data.validated_data["due_date"],
            paid_on=data.validated_data.get("paid_on") or timezone.localdate(),
            amount=data.validated_data.get("amount"),
            wallet=data.validated_data.get("wallet"),
        )
        return Response(
            TransactionSerializer(payment.transaction, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def unpay(self, request, pk=None):
        bill = self.get_object()
        due = serializers.DateField().to_internal_value(request.data.get("due_date"))
        services.unpay_bill(get_object_or_404(BillPayment, bill=bill, due_date=due))
        return Response(status=status.HTTP_204_NO_CONTENT)


class SplitRuleViewSet(OwnedViewSet):
    serializer_class = SplitRuleSerializer
    pagination_class = None

    def queryset_for(self, user):
        return selectors.split_rules(user)

    def perform_create(self, serializer):
        serializer.instance = services.save_rule(
            SplitRule(owner=self.request.user, **serializer.validated_data)
        )

    def perform_update(self, serializer):
        rule = serializer.instance
        for name, value in serializer.validated_data.items():
            setattr(rule, name, value)
        services.save_rule(rule)


class PaydayView(APIView):
    """GET ?amount=25000 previews the split; POST records the pay and applies it."""

    def get(self, request):
        try:
            amount = Decimal(request.query_params.get("amount", ""))
        except InvalidOperation as exc:
            raise serializers.ValidationError({"amount": "Enter the amount received."}) from exc
        if not amount.is_finite() or amount <= 0 or amount >= Decimal("1e10"):
            raise serializers.ValidationError({"amount": "Enter the amount received."})
        lines = services.preview_split(request.user, amount.quantize(Decimal("0.01")))
        total = sum((line["amount"] for line in lines), Decimal("0"))
        return Response(
            {
                "lines": [
                    {
                        "rule_id": line["rule"].pk,
                        "name": line["rule"].name,
                        "amount": str(line["amount"]),
                        "to_wallet": line["rule"].to_wallet_id,
                        "category": line["rule"].category_id,
                    }
                    for line in lines
                ],
                "allocated": str(total),
                "remaining": str(amount.quantize(Decimal("0.01")) - total),
            }
        )

    def post(self, request):
        data = ReceivePaySerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        values = data.validated_data
        split = services.receive_pay(
            owner=request.user,
            amount=values["amount"],
            wallet=values["wallet"],
            date=values.get("date") or timezone.localdate(),
            category=values.get("category"),
            note=values.get("note") or "Sahod",
        )
        context = {"request": request}
        return Response(
            {
                "income": TransactionSerializer(split.income, context=context).data,
                "moves": TransactionSerializer(
                    [line.transaction for line in split.lines.select_related("transaction")],
                    many=True,
                    context=context,
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )
