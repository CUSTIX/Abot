"""Writes and rules for wallets, categories and transactions."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.db.models import ProtectedError, Q, RestrictedError

from money.models import Category, Transaction, Wallet

STARTER_WALLETS = [
    ("Cash", Wallet.Kind.CASH, True, "#b45309"),
    ("GCash", Wallet.Kind.EWALLET, True, "#2563eb"),
    ("Maya", Wallet.Kind.EWALLET, True, "#059669"),
    ("Bank", Wallet.Kind.BANK, True, "#7c3aed"),
    ("Savings", Wallet.Kind.SAVINGS, False, "#0f766e"),
]

STARTER_CATEGORIES = [
    (
        "expense",
        "Food & drinks",
        "🍜",
        "kape, coffee, lunch, dinner, breakfast, almusal, ulam, "
        "meryenda, merienda, jollibee, mcdo, food, milktea, milk tea, snack, kain",
    ),
    ("expense", "Groceries", "🛒", "grocery, groceries, palengke, puregold, savemore, bigas, rice"),
    (
        "expense",
        "Transport",
        "🚌",
        "jeep, jeepney, grab, taxi, mrt, lrt, bus, angkas, joyride, "
        "fare, pamasahe, tricycle, trike, gas, gasolina, parking",
    ),
    (
        "expense",
        "Bills",
        "⚡",
        "meralco, kuryente, electric, tubig, water, internet, wifi, pldt, "
        "converge, rent, upa, bill",
    ),
    ("expense", "Load & data", "📱", "load, data, globe, smart, tnt, gomo, dito"),
    ("expense", "Padala", "💌", "padala, family, nanay, tatay, mama, papa, allowance"),
    ("expense", "Shopping", "🛍️", "shopee, lazada, shein, shirt, shoes, damit"),
    ("expense", "Health", "💊", "gamot, meds, medicine, doctor, pharmacy, mercury, checkup"),
    ("expense", "Fun", "🎉", "movie, sine, netflix, spotify, games, inom, gimik, concert"),
    ("expense", "Other", "📦", ""),
    ("income", "Salary", "💼", "sahod, salary, payroll, sweldo"),
    ("income", "Side hustle", "🧑‍💻", "freelance, raket, commission, sideline, client"),
    ("income", "Gifts", "🎁", "gift, regalo, aguinaldo, bonus"),
    ("income", "Other income", "🪙", ""),
]


def create_starter_set(user) -> None:
    Wallet.objects.bulk_create(
        Wallet(owner=user, name=n, kind=k, spendable=s, color=c, sort_order=i)
        for i, (n, k, s, c) in enumerate(STARTER_WALLETS)
    )
    Category.objects.bulk_create(
        Category(owner=user, kind=k, name=n, emoji=e, keywords=w)
        for k, n, e, w in STARTER_CATEGORIES
    )


def _check_owner(user, *objects) -> None:
    for obj in objects:
        if obj is not None and obj.owner_id != user.pk:
            # Never reveal that the object exists for someone else.
            raise ValidationError("Not found.")


def validate_transaction(
    *, owner, kind: str, amount: Decimal, wallet, to_wallet=None, category=None
) -> None:
    _check_owner(owner, wallet, to_wallet, category)
    if amount is None or amount <= 0:
        raise ValidationError({"amount": "The amount must be more than zero."})
    if kind == Transaction.Kind.TRANSFER:
        if to_wallet is None:
            raise ValidationError({"to_wallet": "Pick where the money goes."})
        if to_wallet.pk == wallet.pk:
            raise ValidationError({"to_wallet": "Pick two different wallets."})
        if category is not None:
            raise ValidationError({"category": "Transfers don't have a category."})
    else:
        if to_wallet is not None:
            raise ValidationError({"to_wallet": "Only transfers have a destination wallet."})
        if category is not None and category.kind != kind:
            raise ValidationError({"category": f"Pick an {kind} category."})
    for w in (wallet, to_wallet):
        if w is not None and w.archived:
            raise ValidationError({"wallet": f"{w.name} is archived."})


def record(*, owner, kind, amount, date, wallet, to_wallet=None, category=None, note=""):
    validate_transaction(
        owner=owner, kind=kind, amount=amount, wallet=wallet, to_wallet=to_wallet, category=category
    )
    return Transaction.objects.create(
        owner=owner,
        kind=kind,
        amount=amount,
        date=date,
        wallet=wallet,
        to_wallet=to_wallet,
        category=category,
        note=note.strip(),
    )


def record_neutral(
    *, owner, kind: str, amount, date, wallet, note: str, source: str
) -> Transaction:
    """A money move that isn't spending or income (lending, paying back, a paluwagan share).
    It changes the wallet's balance; reports and "spent today" ignore it."""
    if kind not in (Transaction.Kind.EXPENSE, Transaction.Kind.INCOME):
        raise ValidationError({"kind": "Neutral moves are money out or money in."})
    validate_transaction(owner=owner, kind=kind, amount=amount, wallet=wallet)
    return Transaction.objects.create(
        owner=owner,
        kind=kind,
        amount=amount,
        date=date,
        wallet=wallet,
        note=note.strip()[:120],
        neutral=True,
        source=source,
    )


SOURCE_LABELS = {"utang": "Utang", "paluwagan": "Paluwagan"}


def _check_editable(txn: Transaction) -> None:
    if txn.source:
        where = SOURCE_LABELS.get(txn.source, txn.source)
        raise ValidationError({"detail": f"This belongs to {where}. Change it there."})


def update(txn: Transaction, **fields) -> Transaction:
    _check_editable(txn)
    for name, value in fields.items():
        setattr(txn, name, value)
    if txn.kind == Transaction.Kind.TRANSFER:
        txn.category = None
    else:
        txn.to_wallet = None
    validate_transaction(
        owner=txn.owner,
        kind=txn.kind,
        amount=txn.amount,
        wallet=txn.wallet,
        to_wallet=txn.to_wallet,
        category=txn.category,
    )
    txn.note = txn.note.strip()
    txn.save()
    return txn


def delete(txn: Transaction, *, owned_by: str = "") -> None:
    """Delete a transaction. Utang/paluwagan moves can only be deleted by their own module."""
    if txn.source != owned_by:
        _check_editable(txn)
    txn.delete()


def save_wallet(wallet: Wallet) -> Wallet:
    if (
        Wallet.objects.filter(owner=wallet.owner, name__iexact=wallet.name)
        .exclude(pk=wallet.pk)
        .exists()
    ):
        raise ValidationError({"name": "You already have a wallet with that name."})
    wallet.save()
    return wallet


@db_transaction.atomic
def delete_wallet(wallet: Wallet) -> str:
    """A wallet with history is archived (its past stays correct); an unused one is deleted."""
    used = Transaction.objects.filter(Q(wallet=wallet) | Q(to_wallet=wallet)).exists()
    if not used:
        try:
            with db_transaction.atomic():
                wallet.delete()
            return "deleted"
        except (RestrictedError, ProtectedError):
            pass  # a bill or paluwagan still pays from it: keep it, archived
    wallet.archived = True
    wallet.save(update_fields=["archived", "updated_at"])
    return "archived"


def save_category(category: Category) -> Category:
    if (
        Category.objects.filter(
            owner=category.owner, kind=category.kind, name__iexact=category.name
        )
        .exclude(pk=category.pk)
        .exists()
    ):
        raise ValidationError({"name": "You already have a category with that name."})
    category.save()
    return category
