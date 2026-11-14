from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.models import OwnedModel, TimeStampedModel
from planning import cycle

MONEY = {"max_digits": 12, "decimal_places": 2}
DAY = [MinValueValidator(1), MaxValueValidator(31)]


class PaySchedule(TimeStampedModel):
    """When this person gets paid. One per user."""

    class Frequency(models.TextChoices):
        SEMI_MONTHLY = cycle.SEMI_MONTHLY, "Twice a month (kinsenas)"
        MONTHLY = cycle.MONTHLY, "Monthly"
        WEEKLY = cycle.WEEKLY, "Weekly"

    class WeekendRule(models.TextChoices):
        BEFORE = cycle.SHIFT_BEFORE, "Paid the Friday before"
        AFTER = cycle.SHIFT_AFTER, "Paid the Monday after"
        NONE = cycle.SHIFT_NONE, "Paid on the day itself"

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pay_schedule"
    )
    frequency = models.CharField(
        max_length=12, choices=Frequency.choices, default=Frequency.SEMI_MONTHLY
    )
    first_day = models.PositiveSmallIntegerField(default=15, validators=DAY)
    second_day = models.PositiveSmallIntegerField(default=30, validators=DAY)
    weekday = models.PositiveSmallIntegerField(
        default=4, validators=[MaxValueValidator(6)], help_text="0 = Monday … 6 = Sunday"
    )
    weekend_rule = models.CharField(
        max_length=6, choices=WeekendRule.choices, default=WeekendRule.BEFORE
    )
    expected_pay = models.DecimalField(**MONEY, default=Decimal("0"))
    keep_aside = models.DecimalField(
        **MONEY, default=Decimal("0"), help_text="A buffer never counted as safe to spend."
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(first_day__gte=1, first_day__lte=31, second_day__gte=1)
                & Q(second_day__lte=31, weekday__lte=6),
                name="payschedule_days_valid",
            ),
            models.CheckConstraint(
                condition=Q(expected_pay__gte=0, keep_aside__gte=0),
                name="payschedule_amounts_not_negative",
            ),
        ]

    def as_schedule(self) -> cycle.Schedule:
        return cycle.Schedule(
            frequency=self.frequency,
            first_day=self.first_day,
            second_day=self.second_day,
            weekday=self.weekday,
            weekend_rule=self.weekend_rule,
        )


class Bill(OwnedModel):
    """A monthly bill: Meralco, rent, internet... Due on `due_day` (clamped to short months)."""

    name = models.CharField(max_length=40)
    amount = models.DecimalField(**MONEY)
    due_day = models.PositiveSmallIntegerField(validators=DAY)
    wallet = models.ForeignKey("money.Wallet", on_delete=models.RESTRICT, related_name="+")
    category = models.ForeignKey(
        "money.Category", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("due_day", "name")
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="bill_unique_name"),
            models.CheckConstraint(
                condition=Q(amount__gt=0) & Q(due_day__gte=1, due_day__lte=31),
                name="bill_amount_and_day_valid",
                violation_error_message="A bill needs an amount above zero and a day 1-31.",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class BillPayment(models.Model):
    """Marks one due date of a bill as paid, by the expense that paid it."""

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="payments")
    due_date = models.DateField()
    transaction = models.OneToOneField(
        "money.Transaction", on_delete=models.CASCADE, related_name="bill_payment"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["bill", "due_date"], name="billpayment_once_per_due")
        ]

    def __str__(self) -> str:
        return f"{self.bill} due {self.due_date}"


class SplitRule(OwnedModel):
    """Payday split: move part of each salary to a wallet (e.g. Savings) or spend it on a
    category straight away (e.g. Padala)."""

    class Mode(models.TextChoices):
        FIXED = "fixed", "Fixed amount"
        PERCENT = "percent", "Percent of pay"

    name = models.CharField(max_length=40)
    mode = models.CharField(max_length=7, choices=Mode.choices, default=Mode.FIXED)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    to_wallet = models.ForeignKey(
        "money.Wallet", null=True, blank=True, on_delete=models.RESTRICT, related_name="+"
    )
    category = models.ForeignKey(
        "money.Category", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = [
            models.CheckConstraint(
                condition=(Q(to_wallet__isnull=False) & Q(category__isnull=True))
                | (Q(to_wallet__isnull=True) & Q(category__isnull=False)),
                name="splitrule_one_target",
                violation_error_message="Send it to a wallet or spend it on a category, not both.",
            ),
            models.CheckConstraint(
                condition=Q(value__gt=0) & (Q(mode="fixed") | Q(value__lte=100)),
                name="splitrule_value_valid",
                violation_error_message="Use an amount above zero, or a percent from 1 to 100.",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class PaydaySplit(OwnedModel):
    """One salary received and split by the rules. Its money moves are "planned", not spending:
    they don't count against today's safe-to-spend."""

    income = models.OneToOneField(
        "money.Transaction", on_delete=models.CASCADE, related_name="payday_split"
    )

    def __str__(self) -> str:
        return f"Payday {self.income.date}"


class SplitLine(models.Model):
    split = models.ForeignKey(PaydaySplit, on_delete=models.CASCADE, related_name="lines")
    rule = models.ForeignKey(SplitRule, null=True, on_delete=models.SET_NULL, related_name="+")
    transaction = models.OneToOneField(
        "money.Transaction", on_delete=models.CASCADE, related_name="split_line"
    )

    def __str__(self) -> str:
        return f"{self.split} line {self.pk}"


class Goal(OwnedModel):
    """An ipon goal: reach `target` in a savings wallet by `target_date`. Progress is that
    wallet's balance, so moving money there (payday split, transfers) is how you save."""

    name = models.CharField(max_length=40)
    emoji = models.CharField(max_length=8, blank=True)
    target = models.DecimalField(**MONEY)
    target_date = models.DateField()
    wallet = models.ForeignKey("money.Wallet", on_delete=models.RESTRICT, related_name="+")

    class Meta:
        ordering = ("target_date", "id")
        constraints = [
            models.CheckConstraint(
                condition=Q(target__gt=0),
                name="goal_target_positive",
                violation_error_message="The target must be more than zero.",
            )
        ]

    def __str__(self) -> str:
        return self.name
