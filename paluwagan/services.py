"""Paluwagan: pay your share every round, receive the whole pot on your turn.

Shares and the pot are *neutral* money moves (see money.services.record_neutral): they change
wallet balances, but a paluwagan is saving, not spending, so reports never count them.
"""

import datetime as dt

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction as db_transaction

from money import services as money
from paluwagan.models import Paluwagan, PaluwaganEntry
from paluwagan.selectors import rounds


def save(p: Paluwagan) -> Paluwagan:
    if p.wallet.owner_id != p.owner_id:
        raise ValidationError("Not found.")
    if not p.name.strip():
        raise ValidationError({"name": "Give it a name."})
    if not 2 <= p.members <= 60:
        raise ValidationError({"members": "A paluwagan has 2 to 60 members."})
    if not 1 <= p.my_turn <= p.members:
        raise ValidationError({"my_turn": f"Pick a turn from 1 to {p.members}."})
    if p.pk and p.entries.exists():
        stored = Paluwagan.objects.get(pk=p.pk)
        changed = [
            f
            for f in ("share", "members", "my_turn", "frequency", "start_date")
            if getattr(stored, f) != getattr(p, f)
        ]
        if changed:
            raise ValidationError(
                {"detail": "Shares are already recorded: only the name and wallet can change."}
            )
    p.name = p.name.strip()
    p.save()
    return p


def _round_date(p: Paluwagan, number: int) -> dt.date:
    for r in rounds(p):
        if r["round"] == number:
            return r["date"]
    raise ValidationError({"round": f"Pick a round from 1 to {p.members}."})


@db_transaction.atomic
def record(p: Paluwagan, *, kind: str, round_number: int, date: dt.date, wallet=None):
    """Pay this round's share, or receive the pot (only on my turn)."""
    _round_date(p, round_number)
    wallet = wallet or p.wallet
    if wallet.owner_id != p.owner_id:
        raise ValidationError("Not found.")
    if kind == PaluwaganEntry.Kind.PAYOUT and round_number != p.my_turn:
        raise ValidationError({"round": f"Your turn is round {p.my_turn}."})
    amount = p.share if kind == PaluwaganEntry.Kind.CONTRIBUTION else p.pot
    what = "share" if kind == PaluwaganEntry.Kind.CONTRIBUTION else "my payout"
    txn = money.record_neutral(
        owner=p.owner,
        kind="expense" if kind == PaluwaganEntry.Kind.CONTRIBUTION else "income",
        amount=amount,
        date=date,
        wallet=wallet,
        note=f"{p.name}: {what}, round {round_number}",
        source="paluwagan",
    )
    try:
        with db_transaction.atomic():
            return PaluwaganEntry.objects.create(
                paluwagan=p, round=round_number, kind=kind, date=date, transaction=txn
            )
    except IntegrityError as exc:  # double tap
        raise ValidationError({"round": "That's already recorded."}) from exc


@db_transaction.atomic
def undo(entry: PaluwaganEntry) -> None:
    if entry.transaction:
        money.delete(entry.transaction, owned_by="paluwagan")
    entry.delete()


@db_transaction.atomic
def delete(p: Paluwagan) -> None:
    for entry in p.entries.select_related("transaction"):
        undo(entry)
    p.delete()
