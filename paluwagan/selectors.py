import datetime as dt
from decimal import Decimal

from paluwagan.models import Paluwagan, PaluwaganEntry
from planning import cycle

ZERO = Decimal("0")


def for_owner(owner):
    return (
        Paluwagan.objects.filter(owner=owner).select_related("wallet").prefetch_related("entries")
    )


def pay_schedule(owner) -> cycle.Schedule:
    # Reading the pay schedule through planning's public read function.
    from planning import selectors as planning

    sched = planning.schedule(owner)
    return sched.as_schedule() if sched else cycle.Schedule()


def rounds(p: Paluwagan, schedule: cycle.Schedule | None = None) -> list[dict]:
    """Every round with its date, whether my share is paid, and whether it's my payout."""
    dates = cycle.round_dates(
        p.frequency, p.start_date, p.members, schedule or pay_schedule(p.owner)
    )
    entries = {(e.round, e.kind): e for e in p.entries.all()}
    return [
        {
            "round": i,
            "date": day,
            "paid": (i, PaluwaganEntry.Kind.CONTRIBUTION) in entries,
            "my_turn": i == p.my_turn,
            "received": (i, PaluwaganEntry.Kind.PAYOUT) in entries,
            "contribution_id": getattr(entries.get((i, "contribution")), "pk", None),
            "payout_id": getattr(entries.get((i, "payout")), "pk", None),
        }
        for i, day in enumerate(dates, start=1)
    ]


def summary(p: Paluwagan, today: dt.date, schedule: cycle.Schedule | None = None) -> dict:
    rows = rounds(p, schedule)
    paid = sum(1 for r in rows if r["paid"])
    received = any(r["received"] for r in rows)
    next_due = next((r for r in rows if not r["paid"]), None)
    return {
        "rounds": rows,
        "contributed": p.share * paid,
        "total_to_pay": p.share * p.members,
        "pot": p.pot,
        "my_turn_date": rows[p.my_turn - 1]["date"],
        "received": received,
        "next_due": next_due,
        "finished": paid == p.members and received,
        "behind": sum(1 for r in rows if not r["paid"] and r["date"] < today),
    }


def shares_due_by(owner, last_day: dt.date) -> list[dict]:
    """Unpaid shares dated on or before `last_day` (overdue ones too), set aside like bills."""
    schedule = pay_schedule(owner)
    due = []
    for p in for_owner(owner):
        for r in rounds(p, schedule):
            if not r["paid"] and r["date"] <= last_day:
                due.append({"paluwagan": p, "round": r["round"], "date": r["date"]})
    return sorted(due, key=lambda d: d["date"])
