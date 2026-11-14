"""Utang: lending and borrowing between people, with partial payments.

Money that changes hands is recorded as a *neutral* transaction: it moves the wallet balance
(so safe-to-spend sees it) but is never counted as spending or income.

    lent      -> money out of my wallet now, money back in when they pay
    borrowed  -> money into my wallet now, money out when I pay back
"""

import datetime as dt
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.db.models import Sum

from money import services as money
from utang.models import Utang, UtangPayment

ZERO = Decimal("0")


def paid_total(utang: Utang) -> Decimal:
    return utang.payments.aggregate(t=Sum("amount"))["t"] or ZERO


def _check_wallet(owner, wallet) -> None:
    if wallet is not None and wallet.owner_id != owner.pk:
        raise ValidationError("Not found.")


@db_transaction.atomic
def create(
    *,
    owner,
    person: str,
    direction: str,
    amount: Decimal,
    date: dt.date,
    due_date: dt.date | None = None,
    note: str = "",
    wallet=None,
) -> Utang:
    """`wallet` given: the money moved today through that wallet (lent from / borrowed into).
    No wallet: just keep track of an utang that already exists."""
    person = person.strip()
    if not person:
        raise ValidationError({"person": "Who is it with?"})
    if due_date and due_date < date:
        raise ValidationError({"due_date": "The due date can't be before the utang started."})
    _check_wallet(owner, wallet)
    txn = None
    if wallet is not None:
        lent = direction == Utang.Direction.LENT
        txn = money.record_neutral(
            owner=owner,
            kind="expense" if lent else "income",
            amount=amount,
            date=date,
            wallet=wallet,
            note=f"{'Lent to' if lent else 'Borrowed from'} {person}",
            source="utang",
        )
    return Utang.objects.create(
        owner=owner,
        person=person,
        direction=direction,
        amount=amount,
        date=date,
        due_date=due_date,
        note=note.strip(),
        transaction=txn,
    )


@db_transaction.atomic
def add_payment(utang: Utang, *, amount: Decimal, date: dt.date, wallet=None) -> UtangPayment:
    """A repayment, full or partial. It can't be more than what's still owed."""
    utang = Utang.objects.select_for_update().get(pk=utang.pk)  # two quick taps can't overpay
    remaining = utang.amount - paid_total(utang)
    if remaining <= 0:
        raise ValidationError({"amount": "This utang is already fully paid."})
    if amount > remaining:
        raise ValidationError({"amount": f"Only {remaining:,.2f} is still owed."})
    if date < utang.date:
        raise ValidationError({"date": "A payment can't be before the utang started."})
    _check_wallet(utang.owner, wallet)
    txn = None
    if wallet is not None:
        lent = utang.direction == Utang.Direction.LENT
        txn = money.record_neutral(
            owner=utang.owner,
            kind="income" if lent else "expense",
            amount=amount,
            date=date,
            wallet=wallet,
            note=f"{utang.person} paid back" if lent else f"Paid back {utang.person}",
            source="utang",
        )
    return UtangPayment.objects.create(utang=utang, amount=amount, date=date, transaction=txn)


@db_transaction.atomic
def delete_payment(payment: UtangPayment) -> None:
    if payment.transaction:
        money.delete(payment.transaction, owned_by="utang")
    payment.delete()


@db_transaction.atomic
def delete(utang: Utang) -> None:
    """Remove the utang and every money move it made, so balances go back to how they were."""
    for payment in utang.payments.select_related("transaction"):
        delete_payment(payment)
    if utang.transaction:
        money.delete(utang.transaction, owned_by="utang")
    utang.delete()


def update(utang: Utang, *, person=None, due_date=..., note=None) -> Utang:
    """Only the description can change; amounts are fixed by the money that moved."""
    if person is not None:
        if not person.strip():
            raise ValidationError({"person": "Who is it with?"})
        utang.person = person.strip()
    if due_date is not ...:
        if due_date and due_date < utang.date:
            raise ValidationError({"due_date": "The due date can't be before the utang started."})
        utang.due_date = due_date
    if note is not None:
        utang.note = note.strip()
    utang.save()
    return utang
