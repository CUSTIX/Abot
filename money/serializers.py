import re
from decimal import Decimal

from rest_framework import serializers

from core.api import OwnedPrimaryKeyField
from money.models import Category, Transaction, Wallet


class WalletSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = [
            "id",
            "name",
            "kind",
            "opening_balance",
            "spendable",
            "color",
            "archived",
            "sort_order",
            "balance",
        ]

    def get_balance(self, wallet) -> str:
        balances = self.context.get("balances") or {}
        return str(balances.get(wallet.pk, wallet.opening_balance))

    def validate_name(self, value):
        return value.strip()

    def validate_color(self, value):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise serializers.ValidationError("Use a hex colour like #0f766e.")
        return value


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "kind", "emoji", "keywords", "archived"]

    def validate_name(self, value):
        return value.strip()


class TransactionSerializer(serializers.ModelSerializer):
    wallet = OwnedPrimaryKeyField(queryset=Wallet.objects.none())
    to_wallet = OwnedPrimaryKeyField(
        queryset=Wallet.objects.none(), required=False, allow_null=True
    )
    category = OwnedPrimaryKeyField(
        queryset=Category.objects.none(), required=False, allow_null=True
    )
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = Transaction
        fields = [
            "id",
            "kind",
            "amount",
            "date",
            "wallet",
            "to_wallet",
            "category",
            "note",
            "neutral",
            "source",
        ]
        read_only_fields = ["neutral", "source"]

    def to_representation(self, txn):
        data = super().to_representation(txn)
        data["wallet_name"] = txn.wallet.name
        data["to_wallet_name"] = txn.to_wallet.name if txn.to_wallet else None
        data["category_name"] = txn.category.name if txn.category else None
        data["category_emoji"] = txn.category.emoji if txn.category else ""
        return data
