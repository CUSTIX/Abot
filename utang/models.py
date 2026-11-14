from django.db import models
from django.db.models import Q

from core.models import OwnedModel

MONEY = {"max_digits": 12, "decimal_places": 2}


class Utang(OwnedModel):
    """Money lent to or borrowed from a person. Repaid in one or more payments."""

    class Direction(models.TextChoices):
        LENT = "lent", "They owe me"
        BORROWED = "borrowed", "I owe them"

    person = models.CharField(max_length=60)
    direction = models.CharField(max_length=8, choices=Direction.choices)
    amount = models.DecimalField(**MONEY)
    date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=120, blank=True)
    # The money that moved when it happened (optional: old utang can be added without it).
    transaction = models.OneToOneField(
        "money.Transaction", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ("-date", "-id")
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="utang_amount_positive",
                violation_error_message="The amount must be more than zero.",
            ),
            models.CheckConstraint(
                condition=Q(due_date__isnull=True) | Q(due_date__gte=models.F("date")),
                name="utang_due_after_date",
                violation_error_message="The due date can't be before the utang started.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.person}: {self.amount}"


class UtangPayment(models.Model):
    utang = models.ForeignKey(Utang, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(**MONEY)
    date = models.DateField()
    transaction = models.OneToOneField(
        "money.Transaction", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ("date", "id")
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="utangpayment_amount_positive")
        ]

    def __str__(self) -> str:
        return f"{self.utang.person} paid {self.amount}"
