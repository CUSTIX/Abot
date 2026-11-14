"""Reads for planning: the "Today" summary, bills in this cycle, and the payday split rules."""

import datetime as dt
from decimal import Decimal

from money import selectors as money
from paluwagan import selectors as paluwagan
from planning import cycle
from planning.models import Bill, BillPayment, Goal, PaySchedule, SplitLine, SplitRule
from utang import selectors as utang

ZERO = Decimal("0")


def schedule(owner) -> PaySchedule | None:
    return PaySchedule.objects.filter(owner=owner).first()


def bills(owner):
    return Bill.objects.filter(owner=owner).select_related("wallet", "category")


def split_rules(owner):
    return SplitRule.objects.filter(owner=owner).select_related("to_wallet", "category")


def bills_in_window(owner, start: dt.date, end: dt.date) -> list[dict]:
    """Every due date of an active bill between start and end, with whether it's paid."""
    active = list(bills(owner).filter(active=True))
    paid = {
        (p.bill_id, p.due_date): p
        for p in BillPayment.objects.filter(bill__in=active, due_date__gte=start, due_date__lte=end)
    }
    rows = []
    for bill in active:
        for due in cycle.bill_due_dates(bill.due_day, start, end):
            payment = paid.get((bill.pk, due))
            rows.append(
                {
                    "bill": bill,
                    "due_date": due,
                    "paid": payment is not None,
                    "payment_id": payment.pk if payment else None,
                }
            )
    return sorted(rows, key=lambda r: (r["due_date"], r["bill"].name))


def planned_transaction_ids(owner, start: dt.date, end: dt.date) -> set[int]:
    """Bill payments and payday-split moves: planned money, not day-to-day spending."""
    bill_txns = BillPayment.objects.filter(
        bill__owner=owner, transaction__date__gte=start, transaction__date__lte=end
    ).values_list("transaction_id", flat=True)
    split_txns = SplitLine.objects.filter(
        split__owner=owner, transaction__date__gte=start, transaction__date__lte=end
    ).values_list("transaction_id", flat=True)
    return set(bill_txns) | set(split_txns)


def upcoming_commitments(owner, last_day: dt.date) -> list[dict]:
    """Other money that must go out before payday, set aside like bills: utang I owe and
    paluwagan shares that are due (or overdue) by then."""
    shares = [
        {
            "kind": "paluwagan",
            "id": row["paluwagan"].pk,
            "label": f"{row['paluwagan'].name} share (round {row['round']})",
            "amount": row["paluwagan"].share,
            "due_date": row["date"],
        }
        for row in paluwagan.shares_due_by(owner, last_day)
    ]
    debts = [
        {
            "kind": "utang",
            "id": row["utang"].pk,
            "label": f"Utang to {row['utang'].person}",
            "amount": row["remaining"],
            "due_date": row["utang"].due_date,
        }
        for row in utang.borrowed_due_by(owner, last_day)
    ]
    return sorted(debts + shares, key=lambda c: c["due_date"])


def today(owner, today: dt.date) -> dict:
    sched = schedule(owner)
    plan = sched.as_schedule() if sched else cycle.Schedule()
    start, next_payday = cycle.current_cycle(plan, today)
    balances = money.balances(owner, as_of=today)
    spendable_ids = list(money.wallets(owner).filter(spendable=True).values_list("pk", flat=True))
    spendable = sum((balances.get(pk, ZERO) for pk in spendable_ids), ZERO)
    last_day = next_payday - dt.timedelta(days=1)
    window = bills_in_window(owner, start, last_day)
    commitments = upcoming_commitments(owner, last_day)
    reserved = sum((r["bill"].amount for r in window if not r["paid"]), ZERO) + sum(
        (c["amount"] for c in commitments), ZERO
    )
    spent_today = money.expense_total(
        owner,
        start=today,
        end=today,
        wallet_ids=spendable_ids,
        exclude_ids=planned_transaction_ids(owner, today, today),
    )
    safe = cycle.safe_to_spend(
        today=today,
        cycle_start=start,
        next_payday=next_payday,
        spendable=spendable,
        bills_reserved=reserved,
        keep_aside=sched.keep_aside if sched else ZERO,
        spent_today=spent_today,
    )
    return {
        "has_schedule": sched is not None,
        "safe": safe,
        "bills": window,
        "commitments": commitments,
        "cycle_spending": money.spending_by_category(owner, start=start, end=today)[:6],
        "recent": list(money.transactions(owner)[:6]),
    }


def goals(owner, today: dt.date) -> list[dict]:
    """Each ipon goal with progress (its wallet's balance) and how much to save per payday.
    Goals sharing a wallet are filled in order of target date."""
    sched = schedule(owner)
    plan = sched.as_schedule() if sched else cycle.Schedule()
    balances = money.balances(owner, as_of=today)
    left_in_wallet: dict[int, Decimal] = {}
    rows = []
    for goal in Goal.objects.filter(owner=owner).select_related("wallet"):
        wallet_balance = max(balances.get(goal.wallet_id, ZERO), ZERO)
        available = left_in_wallet.get(goal.wallet_id, wallet_balance)
        saved = min(available, goal.target)
        left_in_wallet[goal.wallet_id] = available - saved
        missing = goal.target - saved
        paydays = cycle.paydays_until(plan, today, goal.target_date)
        status = "done" if missing <= 0 else ("late" if goal.target_date < today else "saving")
        rows.append(
            {
                "goal": goal,
                "saved": saved,
                "missing": missing,
                "paydays_left": len(paydays),
                "per_payday": cycle.per_payday(missing, len(paydays)),
                "status": status,
            }
        )
    return rows


def cycle_report(owner, today: dt.date) -> dict:
    """This pay cycle so far next to the whole previous cycle: income, spending, what you kept,
    and how each category moved."""
    sched = schedule(owner)
    plan = sched.as_schedule() if sched else cycle.Schedule()
    start, next_payday = cycle.current_cycle(plan, today)
    prev_start, _ = cycle.current_cycle(plan, start - dt.timedelta(days=1))
    prev_end = start - dt.timedelta(days=1)

    now, before = (
        money.totals(owner, start=start, end=today),
        money.totals(owner, start=prev_start, end=prev_end),
    )
    previous_rows = money.spending_by_category(owner, start=prev_start, end=prev_end)
    previous = {r["name"]: r["total"] for r in previous_rows}
    current = money.spending_by_category(owner, start=start, end=today)
    seen = {r["name"] for r in current}
    names = [r["name"] for r in current] + [n for n in previous if n not in seen]
    emoji = {r["name"]: r["emoji"] for r in [*previous_rows, *current]}
    days = (today - start).days + 1
    return {
        "start": start,
        "end": today,
        "next_payday": next_payday,
        "days": days,
        "income": now["income"],
        "spending": now["spending"],
        "kept": now["income"] - now["spending"],
        "daily_average": (now["spending"] / days).quantize(Decimal("0.01")),
        "categories": [
            {
                "name": name,
                "emoji": emoji.get(name, ""),
                "total": next((r["total"] for r in current if r["name"] == name), ZERO),
                "previous": previous.get(name, ZERO),
            }
            for name in names
        ],
        "biggest": list(money.biggest_expenses(owner, start=start, end=today)),
        "previous": {
            "start": prev_start,
            "end": prev_end,
            "days": (prev_end - prev_start).days + 1,
            "income": before["income"],
            "spending": before["spending"],
            "kept": before["income"] - before["spending"],
        },
    }
