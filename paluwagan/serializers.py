from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from core.api import OwnedPrimaryKeyField
from money.models import Wallet
from paluwagan import selectors
from paluwagan.models import Paluwagan


class PaluwaganSerializer(serializers.ModelSerializer):
    share = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    wallet = OwnedPrimaryKeyField(queryset=Wallet.objects.none())

    class Meta:
        model = Paluwagan
        fields = ["id", "name", "share", "members", "my_turn", "frequency", "start_date", "wallet"]

    def to_representation(self, p):
        data = super().to_representation(p)
        s = selectors.summary(p, timezone.localdate(), self.context.get("schedule"))
        next_due = s["next_due"]
        data.update(
            {
                "pot": str(s["pot"]),
                "contributed": str(s["contributed"]),
                "total_to_pay": str(s["total_to_pay"]),
                "my_turn_date": s["my_turn_date"],
                "received": s["received"],
                "finished": s["finished"],
                "behind": s["behind"],
                "next_due": {"round": next_due["round"], "date": next_due["date"]}
                if next_due
                else None,
                "rounds": s["rounds"],
            }
        )
        return data


class RecordSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["contribution", "payout"])
    round = serializers.IntegerField(min_value=1, max_value=60)
    date = serializers.DateField(required=False)
    wallet = OwnedPrimaryKeyField(queryset=Wallet.objects.none(), required=False)
