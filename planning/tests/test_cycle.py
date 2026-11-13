"""Pay-cycle math: paydays, short months, weekend rules, bills and safe-to-spend."""

import datetime as dt
from decimal import Decimal

import pytest

from planning import cycle
from planning.cycle import Schedule

D, date = Decimal, dt.date


@pytest.mark.parametrize(
    "year,month,day,expected",
    [
        (2026, 2, 30, date(2026, 2, 28)),
        (2028, 2, 30, date(2028, 2, 29)),  # leap year
        (2026, 4, 31, date(2026, 4, 30)),
        (2026, 1, 15, date(2026, 1, 15)),
    ],
)
def test_clamp_day_to_short_months(year, month, day, expected):
    assert cycle.clamp_day(year, month, day) == expected


@pytest.mark.parametrize(
    "rule,expected",
    [
        ("before", date(2026, 11, 13)),  # Sun 15 -> Fri 13
        ("after", date(2026, 11, 16)),  # Sun 15 -> Mon 16
        ("none", date(2026, 11, 15)),
    ],
)
def test_weekend_paydays_move(rule, expected):
    assert date(2026, 11, 15).weekday() == 6
    assert cycle.shift_weekend(date(2026, 11, 15), rule) == expected


def test_weekday_paydays_never_move():
    assert cycle.shift_weekend(date(2026, 11, 30), "before") == date(2026, 11, 30)  # Monday


def test_kinsenas_cycle_mid_month():
    s = Schedule(weekend_rule="none")
    assert cycle.current_cycle(s, date(2026, 11, 20)) == (date(2026, 11, 15), date(2026, 11, 30))
    assert cycle.current_cycle(s, date(2026, 11, 3)) == (date(2026, 10, 30), date(2026, 11, 15))


def test_payday_itself_starts_the_new_cycle():
    s = Schedule(weekend_rule="none")
    assert cycle.current_cycle(s, date(2026, 11, 15)) == (date(2026, 11, 15), date(2026, 11, 30))
    assert cycle.current_cycle(s, date(2026, 11, 14)) == (date(2026, 10, 30), date(2026, 11, 15))


def test_february_and_year_end():
    s = Schedule(weekend_rule="none")
    assert cycle.current_cycle(s, date(2027, 2, 20)) == (date(2027, 2, 15), date(2027, 2, 28))
    assert cycle.current_cycle(s, date(2026, 12, 31)) == (date(2026, 12, 30), date(2027, 1, 15))


def test_friday_before_rule_moves_the_cycle_boundary():
    # Nov 15, 2026 is a Sunday: paid Friday the 13th.
    s = Schedule(weekend_rule="before")
    assert cycle.current_cycle(s, date(2026, 11, 13)) == (date(2026, 11, 13), date(2026, 11, 30))
    assert cycle.current_cycle(s, date(2026, 11, 12))[1] == date(2026, 11, 13)


def test_monthly_and_weekly():
    monthly = Schedule(frequency="monthly", first_day=25, weekend_rule="none")
    assert cycle.current_cycle(monthly, date(2026, 11, 3)) == (
        date(2026, 10, 25),
        date(2026, 11, 25),
    )
    weekly = Schedule(frequency="weekly", weekday=4)  # Fridays
    assert cycle.current_cycle(weekly, date(2026, 11, 18)) == (
        date(2026, 11, 13),
        date(2026, 11, 20),
    )
    assert cycle.current_cycle(weekly, date(2026, 11, 20)) == (
        date(2026, 11, 20),
        date(2026, 11, 27),
    )


def test_bill_due_dates_clamp_and_span_months():
    assert cycle.bill_due_dates(31, date(2026, 1, 20), date(2026, 3, 5)) == [
        date(2026, 1, 31),
        date(2026, 2, 28),
    ]
    assert cycle.bill_due_dates(10, date(2026, 11, 15), date(2026, 11, 29)) == []


def safe(**overrides):
    params = {
        "today": date(2026, 11, 20),
        "cycle_start": date(2026, 11, 15),
        "next_payday": date(2026, 11, 30),
        "spendable": D("10000"),
        "bills_reserved": D("0"),
        "keep_aside": D("0"),
        "spent_today": D("0"),
    }
    return cycle.safe_to_spend(**{**params, **overrides})


def test_safe_to_spend_spreads_money_over_days_left():
    result = safe()
    assert result.days_left == 10
    assert result.per_day == D("1000.00") and result.left_today == D("1000.00")
    assert result.status == "ok"


def test_bills_and_buffer_are_set_aside_first():
    result = safe(bills_reserved=D("3000"), keep_aside=D("1000"))
    assert result.free_until_payday == D("6000")
    assert result.per_day == D("600.00")


def test_spending_today_does_not_shrink_todays_budget():
    # 9,600 left after spending 400 today: today's budget stays 1,000, with 600 left.
    result = safe(spendable=D("9600"), spent_today=D("400"))
    assert result.per_day == D("1000.00") and result.left_today == D("600.00")
    assert result.status == "ok"


@pytest.mark.parametrize("spent,status", [(D("600"), "tight"), (D("1200"), "over"), (D("0"), "ok")])
def test_status(spent, status):
    assert safe(spendable=D("10000") - spent, spent_today=spent).status == status


def test_bills_bigger_than_the_money_mean_short():
    result = safe(spendable=D("2000"), bills_reserved=D("3500"))
    assert result.status == "short" and result.per_day == 0
    assert result.free_until_payday == D("-1500")


def test_last_day_before_payday_counts_as_one_day():
    result = safe(today=date(2026, 11, 29), spendable=D("700"))
    assert result.days_left == 1 and result.per_day == D("700.00")


def test_per_day_rounds_down_to_the_centavo():
    assert safe(today=date(2026, 11, 27), spendable=D("1000")).per_day == D("333.33")


def test_split_amounts():
    rules = [("fixed", D("3000")), ("percent", D("20")), ("percent", D("12.5"))]
    assert cycle.split_amounts(D("20000"), rules) == [D("3000.00"), D("4000.00"), D("2500.00")]
    with pytest.raises(ValueError, match="more than"):
        cycle.split_amounts(D("5000"), [("fixed", D("3000")), ("percent", D("50"))])
