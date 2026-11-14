"""Paluwagan: rounds on paydays, shares and the pot as neutral money moves."""

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from money import selectors as money
from money.models import Transaction

D = Decimal
pytestmark = pytest.mark.django_db


@pytest.fixture
def today(monkeypatch):
    fixed = dt.date(2026, 11, 20)
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: fixed)
    return fixed


@pytest.fixture
def no_weekend_shift(api):
    api.put(
        "/api/schedule/",
        {
            "frequency": "semi_monthly",
            "first_day": 15,
            "second_day": 30,
            "weekday": 4,
            "weekend_rule": "none",
            "expected_pay": "0",
            "keep_aside": "0",
        },
        format="json",
    )


def create(api, wallets, **extra):
    body = {
        "name": "Office paluwagan",
        "share": "1000",
        "members": 5,
        "my_turn": 3,
        "frequency": "payday",
        "start_date": "2026-11-15",
        "wallet": wallets["GCash"].pk,
        **extra,
    }
    return api.post("/api/paluwagan/", body, format="json")


def test_rounds_follow_my_paydays(api, today, wallets, no_weekend_shift):
    data = create(api, wallets).json()
    assert [r["date"] for r in data["rounds"]] == [
        "2026-11-15",
        "2026-11-30",
        "2026-12-15",
        "2026-12-30",
        "2027-01-15",
    ]
    assert data["pot"] == "5000.00" and data["my_turn_date"] == "2026-12-15"
    assert data["next_due"] == {"round": 1, "date": "2026-11-15"}
    assert data["behind"] == 1  # round 1 (Nov 15) is past and unpaid


def test_paying_shares_and_receiving_the_pot(api, today, wallets, no_weekend_shift):
    api.post(
        "/api/transactions/",
        {"kind": "income", "amount": "3000", "date": "2026-11-15", "wallet": wallets["GCash"].pk},
        format="json",
    )
    pid = create(api, wallets).json()["id"]
    paid = api.post(
        f"/api/paluwagan/{pid}/record/", {"kind": "contribution", "round": 1}, format="json"
    )
    assert paid.status_code == 201 and paid.json()["contributed"] == "1000.00"
    assert money.balances(api.user)[wallets["GCash"].pk] == D("2000")
    again = api.post(
        f"/api/paluwagan/{pid}/record/", {"kind": "contribution", "round": 1}, format="json"
    )
    assert again.status_code == 400
    not_mine = api.post(
        f"/api/paluwagan/{pid}/record/", {"kind": "payout", "round": 2}, format="json"
    )
    assert not_mine.status_code == 400 and "round 3" in str(not_mine.json())
    pot = api.post(f"/api/paluwagan/{pid}/record/", {"kind": "payout", "round": 3}, format="json")
    assert pot.json()["received"] is True
    assert money.balances(api.user)[wallets["GCash"].pk] == D("7000")
    spending = api.get("/api/spending/?start=2026-11-01&end=2026-11-30").json()
    assert spending["total"] == "0"  # saving, not spending
    assert Transaction.objects.filter(source="paluwagan").count() == 2


def test_unpaid_shares_due_before_payday_are_set_aside(api, today, wallets, no_weekend_shift):
    before = api.get("/api/today/").json()
    create(api, wallets)  # round 1 overdue (Nov 15); round 2 is on payday (Nov 30): not before it
    after = api.get("/api/today/").json()
    assert D(after["bills_reserved"]) - D(before["bills_reserved"]) == D("1000")
    assert after["commitments"][0]["label"] == "Office paluwagan share (round 1)"
    assert after["commitments"][0]["overdue"] is True


def test_undo_and_delete_put_balances_back(api, today, wallets, no_weekend_shift):
    pid = create(api, wallets).json()["id"]
    data = api.post(
        f"/api/paluwagan/{pid}/record/", {"kind": "contribution", "round": 1}, format="json"
    ).json()
    entry = data["rounds"][0]["contribution_id"]
    assert api.delete(f"/api/paluwagan/{pid}/entries/{entry}/").status_code == 204
    api.post(f"/api/paluwagan/{pid}/record/", {"kind": "contribution", "round": 1}, format="json")
    assert api.delete(f"/api/paluwagan/{pid}/").status_code == 204
    assert money.balances(api.user)[wallets["GCash"].pk] == D("0")
    assert not Transaction.objects.filter(source="paluwagan").exists()


def test_terms_lock_once_shares_are_recorded(api, today, wallets, no_weekend_shift):
    pid = create(api, wallets).json()["id"]
    assert api.patch(f"/api/paluwagan/{pid}/", {"share": "500"}, format="json").status_code == 200
    api.post(f"/api/paluwagan/{pid}/record/", {"kind": "contribution", "round": 1}, format="json")
    locked = api.patch(f"/api/paluwagan/{pid}/", {"share": "800"}, format="json")
    assert locked.status_code == 400
    assert (
        api.patch(f"/api/paluwagan/{pid}/", {"name": "Barkada"}, format="json").status_code == 200
    )


@pytest.mark.parametrize(
    "extra,field",
    [
        ({"my_turn": 6}, "my_turn"),
        ({"members": 1}, "members"),
        ({"share": "0"}, "share"),
        ({"frequency": "daily"}, "frequency"),
    ],
)
def test_validation(api, today, wallets, extra, field):
    response = create(api, wallets, **extra)
    assert response.status_code == 400 and field in response.json()


def test_weekly_and_monthly_rounds(api, today, wallets):
    weekly = create(api, wallets, frequency="weekly", start_date="2026-11-06").json()
    assert [r["date"] for r in weekly["rounds"]][:2] == ["2026-11-06", "2026-11-13"]
    monthly = create(api, wallets, name="M", frequency="monthly", start_date="2026-01-31").json()
    assert [r["date"] for r in monthly["rounds"]][:2] == ["2026-01-31", "2026-02-28"]


def test_paluwagan_is_private(api, other_api, today, wallets):
    pid = create(api, wallets).json()["id"]
    assert other_api.get(f"/api/paluwagan/{pid}/").status_code == 404
    rec = other_api.post(
        f"/api/paluwagan/{pid}/record/", {"kind": "contribution", "round": 1}, format="json"
    )
    assert rec.status_code == 404
    assert create(other_api, wallets).status_code == 400  # someone else's wallet
