"""Reads for wallets, categories and transactions. Every function is scoped to one owner."""

import datetime as dt
from decimal import Decimal

from django.db.models import Count, DecimalField, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce

from money.models import Category, Transaction, Wallet

ZERO = Decimal("0")
_SUM = {"output_field": DecimalField(max_digits=14, decimal_places=2)}


def wallets(owner, *, include_archived: bool = False) -> QuerySet[Wallet]:
    qs = Wallet.objects.filter(owner=owner)
    return qs if include_archived else qs.filter(archived=False)


def categories(owner, *, kind: str = "") -> QuerySet[Category]:
    qs = Category.objects.filter(owner=owner, archived=False)
    return qs.filter(kind=kind) if kind else qs


def balances(owner, *, as_of: dt.date | None = None) -> dict[int, Decimal]:
    """Balance per wallet id: opening balance + income - expenses - transfers out + transfers in.
    Computed from the ledger (never stored), so it can't drift."""
    txns = Transaction.objects.filter(owner=owner)
    if as_of:
        txns = txns.filter(date__lte=as_of)
    out = dict(
        txns.values("wallet")
        .annotate(
            delta=Coalesce(Sum("amount", filter=Q(kind="income")), Value(ZERO), **_SUM)
            - Coalesce(Sum("amount", filter=~Q(kind="income")), Value(ZERO), **_SUM)
        )
        .values_list("wallet", "delta")
    )
    into = dict(
        txns.filter(kind="transfer")
        .values("to_wallet")
        .annotate(total=Sum("amount"))
        .values_list("to_wallet", "total")
    )
    return {
        w.pk: w.opening_balance + out.get(w.pk, ZERO) + into.get(w.pk, ZERO)
        for w in Wallet.objects.filter(owner=owner)
    }


def transactions(
    owner,
    *,
    kind: str = "",
    wallet_id: int | None = None,
    category_id: int | None = None,
    start: dt.date | None = None,
    end: dt.date | None = None,
    search: str = "",
) -> QuerySet[Transaction]:
    qs = Transaction.objects.filter(owner=owner).select_related("wallet", "to_wallet", "category")
    if kind:
        qs = qs.filter(kind=kind)
    if wallet_id:
        qs = qs.filter(Q(wallet_id=wallet_id) | Q(to_wallet_id=wallet_id))
    if category_id:
        qs = qs.filter(category_id=category_id)
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)
    if search:
        qs = qs.filter(Q(note__icontains=search) | Q(category__name__icontains=search))
    return qs.order_by("-date", "-id")


def expense_total(
    owner, *, start: dt.date, end: dt.date, wallet_ids=None, exclude_ids=()
) -> Decimal:
    qs = Transaction.objects.filter(owner=owner, kind="expense", date__gte=start, date__lte=end)
    if wallet_ids is not None:
        qs = qs.filter(wallet_id__in=wallet_ids)
    if exclude_ids:
        qs = qs.exclude(pk__in=exclude_ids)
    return qs.aggregate(t=Coalesce(Sum("amount"), Value(ZERO), **_SUM))["t"]


def spending_by_category(owner, *, start: dt.date, end: dt.date) -> list[dict]:
    rows = (
        Transaction.objects.filter(owner=owner, kind="expense", date__gte=start, date__lte=end)
        .values("category__id", "category__name", "category__emoji")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    return [
        {
            "category_id": r["category__id"],
            "name": r["category__name"] or "Uncategorised",
            "emoji": r["category__emoji"] or "",
            "total": r["total"],
            "count": r["count"],
        }
        for r in rows
    ]
