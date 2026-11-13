from decimal import Decimal

from django.db import models
from django.db.models import Q

from core.models import OwnedModel

MONEY = {"max_digits": 12, "decimal_places": 2}


class Wallet(OwnedModel):
    """Where money sits: cash, GCash, Maya, a bank account, a savings account."""

    class Kind(models.TextChoices):
        CASH = "cash", "Cash"
        EWALLET = "ewallet", "E-wallet"
        BANK = "bank", "Bank"
        SAVINGS = "savings", "Savings"

    name = models.CharField(max_length=40)
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.CASH)
    opening_balance = models.DecimalField(**MONEY, default=Decimal("0"))
    # Counted in "safe to spend". Savings wallets default to no: that money is spoken for.
    spendable = models.BooleanField(default=True)
    color = models.CharField(max_length=7, default="#0f766e")
    archived = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name")
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="wallet_unique_name"),
            models.CheckConstraint(
                condition=Q(color__regex=r"^#[0-9a-fA-F]{6}$"), name="wallet_color_hex"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Category(OwnedModel):
    class Kind(models.TextChoices):
        EXPENSE = "expense", "Expense"
        INCOME = "income", "Income"

    name = models.CharField(max_length=40)
    kind = models.CharField(max_length=7, choices=Kind.choices, default=Kind.EXPENSE)
    emoji = models.CharField(max_length=8, blank=True)
    # Words that pick this category in quick add ("kape, coffee, starbucks").
    keywords = models.CharField(max_length=300, blank=True)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ("kind", "name")
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(fields=["owner", "kind", "name"], name="category_unique_name")
        ]

    def __str__(self) -> str:
        return self.name


class Transaction(OwnedModel):
    class Kind(models.TextChoices):
        EXPENSE = "expense", "Expense"
        INCOME = "income", "Income"
        TRANSFER = "transfer", "Transfer"

    kind = models.CharField(max_length=8, choices=Kind.choices, db_index=True)
    amount = models.DecimalField(**MONEY)
    date = models.DateField(db_index=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="transactions")
    # Transfers only: where the money went.
    to_wallet = models.ForeignKey(
        Wallet, null=True, blank=True, on_delete=models.PROTECT, related_name="transfers_in"
    )
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions"
    )
    note = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ("-date", "-id")
        indexes = [models.Index(fields=["owner", "date"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="transaction_amount_positive",
                violation_error_message="The amount must be more than zero.",
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind="transfer") & Q(to_wallet__isnull=False) & Q(category__isnull=True)
                )
                | (~Q(kind="transfer") & Q(to_wallet__isnull=True)),
                name="transaction_transfer_shape",
                violation_error_message="A transfer needs a destination wallet and no category.",
            ),
            models.CheckConstraint(
                condition=~Q(wallet=models.F("to_wallet")),
                name="transaction_transfer_not_to_itself",
                violation_error_message="Pick two different wallets for a transfer.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.amount} on {self.date}"
