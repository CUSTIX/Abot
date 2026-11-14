from decimal import Decimal

from rest_framework import serializers

from core.api import OwnedPrimaryKeyField
from money.models import Category, Wallet
from money.serializers import TransactionSerializer
from planning.models import Bill, Goal, PaySchedule, SplitRule

MONEY = {"max_digits": 12, "decimal_places": 2}
CENT = Decimal("0.01")


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaySchedule
        fields = [
            "frequency",
            "first_day",
            "second_day",
            "weekday",
            "weekend_rule",
            "expected_pay",
            "keep_aside",
        ]


class BillSerializer(serializers.ModelSerializer):
    wallet = OwnedPrimaryKeyField(queryset=Wallet.objects.none())
    category = OwnedPrimaryKeyField(
        queryset=Category.objects.none(), required=False, allow_null=True
    )
    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))

    class Meta:
        model = Bill
        fields = ["id", "name", "amount", "due_day", "wallet", "category", "active"]


class PayBillSerializer(serializers.Serializer):
    due_date = serializers.DateField()
    paid_on = serializers.DateField(required=False)
    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"), required=False)
    wallet = OwnedPrimaryKeyField(queryset=Wallet.objects.none(), required=False)


class SplitRuleSerializer(serializers.ModelSerializer):
    to_wallet = OwnedPrimaryKeyField(
        queryset=Wallet.objects.none(), required=False, allow_null=True
    )
    category = OwnedPrimaryKeyField(
        queryset=Category.objects.none(), required=False, allow_null=True
    )
    value = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))

    class Meta:
        model = SplitRule
        fields = ["id", "name", "mode", "value", "to_wallet", "category", "sort_order", "active"]


class ReceivePaySerializer(serializers.Serializer):
    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))
    wallet = OwnedPrimaryKeyField(queryset=Wallet.objects.none())
    date = serializers.DateField(required=False)
    category = OwnedPrimaryKeyField(
        queryset=Category.objects.none(), required=False, allow_null=True
    )
    note = serializers.CharField(max_length=120, required=False, allow_blank=True)


def bill_row(row: dict, today) -> dict:
    bill = row["bill"]
    return {
        "bill_id": bill.pk,
        "name": bill.name,
        "amount": str(bill.amount),
        "due_date": row["due_date"],
        "paid": row["paid"],
        "overdue": not row["paid"] and row["due_date"] < today,
        "payment_id": row["payment_id"],
    }


def today_payload(data: dict, context: dict) -> dict:
    safe = data["safe"]
    money_fields = (
        "spendable",
        "bills_reserved",
        "keep_aside",
        "spent_today",
        "per_day",
        "left_today",
        "free_until_payday",
    )
    return {
        "has_schedule": data["has_schedule"],
        "today": safe.today,
        "cycle_start": safe.cycle_start,
        "next_payday": safe.next_payday,
        "days_left": safe.days_left,
        "status": safe.status,
        **{name: str(getattr(safe, name).quantize(CENT)) for name in money_fields},
        "bills": [bill_row(r, safe.today) for r in data["bills"]],
        "commitments": [
            {
                **c,
                "amount": str(c["amount"].quantize(CENT)),
                "overdue": c["due_date"] < safe.today,
            }
            for c in data["commitments"]
        ],
        "cycle_spending": [
            {**r, "total": str(r["total"].quantize(CENT))} for r in data["cycle_spending"]
        ],
        "recent": TransactionSerializer(data["recent"], many=True, context=context).data,
    }


class GoalSerializer(serializers.ModelSerializer):
    target = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))
    wallet = OwnedPrimaryKeyField(queryset=Wallet.objects.none())

    class Meta:
        model = Goal
        fields = ["id", "name", "emoji", "target", "target_date", "wallet"]


def goal_row(row: dict) -> dict:
    goal = row["goal"]
    return {
        **GoalSerializer(goal).data,
        "wallet_name": goal.wallet.name,
        "saved": str(row["saved"].quantize(CENT)),
        "missing": str(max(row["missing"], Decimal("0")).quantize(CENT)),
        "paydays_left": row["paydays_left"],
        "per_payday": str(row["per_payday"].quantize(CENT)),
        "status": row["status"],
    }
