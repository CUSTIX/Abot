"""Pay-cycle math as pure functions (no database), so every rule is easy to unit test.

A cycle runs from one payday up to the day before the next. "Safe to spend" spreads what you can
freely spend over the days left in the cycle, after setting aside unpaid bills due before the next
payday and an optional buffer.
"""

import calendar
import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

SEMI_MONTHLY, MONTHLY, WEEKLY = "semi_monthly", "monthly", "weekly"
SHIFT_NONE, SHIFT_BEFORE, SHIFT_AFTER = "none", "before", "after"
CENT = Decimal("0.01")


def clamp_day(year: int, month: int, day: int) -> dt.date:
    """Day `day` of the month, or its last day when the month is shorter (a "30th" payday is
    Feb 28/29)."""
    return dt.date(year, month, min(day, calendar.monthrange(year, month)[1]))


def shift_weekend(date: dt.date, rule: str) -> dt.date:
    """Many employers pay on the Friday before (or the Monday after) a weekend payday."""
    if date.weekday() < 5 or rule == SHIFT_NONE:
        return date
    if rule == SHIFT_BEFORE:
        return date - dt.timedelta(days=date.weekday() - 4)
    return date + dt.timedelta(days=7 - date.weekday())


@dataclass(frozen=True)
class Schedule:
    frequency: str = SEMI_MONTHLY
    first_day: int = 15  # semi-monthly and monthly
    second_day: int = 30  # semi-monthly only ("30" means the last day in short months)
    weekday: int = 4  # weekly: 0 = Monday ... 4 = Friday
    weekend_rule: str = SHIFT_BEFORE


def _month_paydays(s: Schedule, year: int, month: int) -> list[dt.date]:
    days = [s.first_day] if s.frequency == MONTHLY else sorted({s.first_day, s.second_day})
    return [shift_weekend(clamp_day(year, month, d), s.weekend_rule) for d in days]


def _add_months(year: int, month: int, n: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + n
    return index // 12, index % 12 + 1


def paydays_around(s: Schedule, today: dt.date) -> list[dt.date]:
    """Sorted paydays from about two months before to two months after `today`."""
    if s.frequency == WEEKLY:
        base = today - dt.timedelta(days=(today.weekday() - s.weekday) % 7)
        return [base + dt.timedelta(weeks=w) for w in range(-8, 9)]
    found = []
    for n in range(-2, 3):
        found += _month_paydays(s, *_add_months(today.year, today.month, n))
    return sorted(set(found))


def current_cycle(s: Schedule, today: dt.date) -> tuple[dt.date, dt.date]:
    """(last payday on or before today, next payday after today)."""
    days = paydays_around(s, today)
    last = max(d for d in days if d <= today)
    nxt = min(d for d in days if d > today)
    return last, nxt


def bill_due_dates(due_day: int, start: dt.date, end: dt.date) -> list[dt.date]:
    """Due dates of a monthly bill (day `due_day`, clamped) between start and end inclusive."""
    dates, (year, month) = [], (start.year, start.month)
    while (year, month) <= (end.year, end.month):
        due = clamp_day(year, month, due_day)
        if start <= due <= end:
            dates.append(due)
        year, month = _add_months(year, month, 1)
    return dates


@dataclass(frozen=True)
class SafeToSpend:
    today: dt.date
    cycle_start: dt.date
    next_payday: dt.date
    days_left: int  # including today, up to the day before payday
    spendable: Decimal  # balance of spendable wallets right now
    bills_reserved: Decimal  # unpaid bills due before the next payday
    keep_aside: Decimal
    spent_today: Decimal
    per_day: Decimal  # today's budget as of this morning
    left_today: Decimal  # per_day - spent_today (negative: overspent today)
    free_until_payday: Decimal  # what's left for everything else after bills and buffer
    status: str  # "ok", "tight" (under 50% of a normal day left), "over" or "short"


def safe_to_spend(
    *,
    today: dt.date,
    cycle_start: dt.date,
    next_payday: dt.date,
    spendable: Decimal,
    bills_reserved: Decimal,
    keep_aside: Decimal,
    spent_today: Decimal,
) -> SafeToSpend:
    days_left = max((next_payday - today).days, 1)
    free = spendable - bills_reserved - keep_aside
    # Today's budget is fixed at the start of the day: add back what was already spent today.
    per_day = ((free + spent_today) / days_left).quantize(CENT, rounding=ROUND_DOWN)
    per_day = max(per_day, Decimal("0"))  # bills and buffer may already take everything
    left_today = per_day - spent_today
    if per_day == 0:
        status = "short"
    elif left_today < 0:
        status = "over"
    elif left_today < per_day / 2:
        status = "tight"
    else:
        status = "ok"
    return SafeToSpend(
        today=today,
        cycle_start=cycle_start,
        next_payday=next_payday,
        days_left=days_left,
        spendable=spendable,
        bills_reserved=bills_reserved,
        keep_aside=keep_aside,
        spent_today=spent_today,
        per_day=per_day,
        left_today=left_today,
        free_until_payday=free,
        status=status,
    )


def split_amounts(amount: Decimal, rules: list[tuple[str, Decimal]]) -> list[Decimal]:
    """Payday split: each rule is ("fixed", ₱) or ("percent", % of the salary). Fixed amounts are
    exact; percentages round down to the centavo. Raises ValueError if they add up to more than
    the salary."""
    parts = []
    for mode, value in rules:
        if mode == "fixed":
            parts.append(value.quantize(CENT))
        else:
            parts.append((amount * value / 100).quantize(CENT, rounding=ROUND_DOWN))
    if sum(parts, Decimal("0")) > amount:
        raise ValueError("The split adds up to more than the amount received.")
    return parts
