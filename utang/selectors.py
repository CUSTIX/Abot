import datetime as dt
from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from utang.models import Utang

ZERO = Decimal("0")


def with_totals(owner):
    """Every utang with `paid` and `remaining`, open ones first (soonest due first)."""
    return (
        Utang.objects.filter(owner=owner)
        .annotate(
            paid=Coalesce(
                Sum("payments__amount"),
                Value(ZERO),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .prefetch_related("payments")
    )


def summary(owner) -> dict:
    rows = list(with_totals(owner))
    owed_to_me = sum((u.amount - u.paid for u in rows if u.direction == "lent"), ZERO)
    i_owe = sum((u.amount - u.paid for u in rows if u.direction == "borrowed"), ZERO)
    return {"owed_to_me": owed_to_me, "i_owe": i_owe}


def borrowed_due_by(owner, end: dt.date) -> list[dict]:
    """What I still owe on utang due on or before `end` (set aside like a bill)."""
    rows = with_totals(owner).filter(
        Q(direction="borrowed"), due_date__isnull=False, due_date__lte=end
    )
    return [
        {"utang": u, "remaining": u.amount - u.paid}
        for u in rows.order_by("due_date")
        if u.amount - u.paid > 0
    ]
