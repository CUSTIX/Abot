from decimal import Decimal

from rest_framework import serializers

from core.api import OwnedPrimaryKeyField
from money.models import Wallet
from utang.models import Utang, UtangPayment

MONEY = {"max_digits": 12, "decimal_places": 2, "min_value": Decimal("0.01")}


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UtangPayment
        fields = ["id", "amount", "date"]


class UtangSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(**MONEY)
    wallet = OwnedPrimaryKeyField(
        queryset=Wallet.objects.none(), write_only=True, required=False, allow_null=True
    )
    paid = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Utang
        fields = [
            "id",
            "person",
            "direction",
            "amount",
            "date",
            "due_date",
            "note",
            "wallet",
            "paid",
            "remaining",
            "payments",
        ]

    def get_paid(self, utang) -> str:
        return str(getattr(utang, "paid", Decimal("0")))

    def get_remaining(self, utang) -> str:
        return str(utang.amount - getattr(utang, "paid", Decimal("0")))


class UtangUpdateSerializer(serializers.Serializer):
    person = serializers.CharField(max_length=60, required=False)
    due_date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(max_length=120, required=False, allow_blank=True)


class AddPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(**MONEY)
    date = serializers.DateField(required=False)
    wallet = OwnedPrimaryKeyField(queryset=Wallet.objects.none(), required=False, allow_null=True)
