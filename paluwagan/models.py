from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from core.models import OwnedModel

MONEY = {"max_digits": 12, "decimal_places": 2}


class Paluwagan(OwnedModel):
    """A rotating savings group: every round each member pays `share`, and one member takes
    the whole pot. My turn is round `my_turn`."""

    class Frequency(models.TextChoices):
        PAYDAY = "payday", "Every payday"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    name = models.CharField(max_length=60)
    share = models.DecimalField(**MONEY)
    members = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2), MaxValueValidator(60)]
    )
    my_turn = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    frequency = models.CharField(max_length=8, choices=Frequency.choices, default=Frequency.PAYDAY)
    start_date = models.DateField()
    wallet = models.ForeignKey("money.Wallet", on_delete=models.RESTRICT, related_name="+")

    class Meta:
        ordering = ("-start_date", "-id")
        constraints = [
            models.CheckConstraint(condition=Q(share__gt=0), name="paluwagan_share_positive"),
            models.CheckConstraint(
                condition=Q(members__gte=2, members__lte=60)
                & Q(my_turn__gte=1, my_turn__lte=F("members")),
                name="paluwagan_turn_in_range",
                violation_error_message="Your turn must be between 1 and the number of members.",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def pot(self):
        return self.share * self.members


class PaluwaganEntry(models.Model):
    """One share paid (contribution) or the pot received (payout), with its money move."""

    class Kind(models.TextChoices):
        CONTRIBUTION = "contribution", "Share paid"
        PAYOUT = "payout", "Pot received"

    paluwagan = models.ForeignKey(Paluwagan, on_delete=models.CASCADE, related_name="entries")
    round = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=12, choices=Kind.choices)
    date = models.DateField()
    transaction = models.OneToOneField(
        "money.Transaction", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ("round", "kind")
        constraints = [
            models.UniqueConstraint(
                fields=["paluwagan", "round", "kind"], name="paluwagan_entry_once"
            )
        ]

    def __str__(self) -> str:
        return f"{self.paluwagan} round {self.round} {self.kind}"
