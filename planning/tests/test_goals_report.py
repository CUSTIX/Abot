"""Ipon goals (per-payday savings) and the cycle report."""

import datetime as dt

import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def today(monkeypatch, api):
    fixed = dt.date(2026, 11, 20)  # cycle Nov 15 -> Nov 30
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: fixed)
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
    return fixed


def add(api, **data):
    return api.post("/api/transactions/", data, format="json").json()


def goal(api, wallets, **extra):
    body = {
        "name": "Siargao",
        "emoji": "🏝️",
        "target": "20000",
        "target_date": "2027-01-15",
        "wallet": wallets["Savings"].pk,
        **extra,
    }
    return api.post("/api/goals/", body, format="json")


def test_goal_says_how_much_to_save_each_payday(api, today, wallets):
    add(api, kind="income", amount="8000", date="2026-11-15", wallet=wallets["Savings"].pk)
    assert goal(api, wallets).status_code == 201
    row = api.get("/api/goals/").json()[0]
    # 12,000 still missing; paydays left: Nov 30, Dec 15, Dec 30, Jan 15 -> 3,000 each.
    assert row["saved"] == "8000.00" and row["missing"] == "12000.00"
    assert row["paydays_left"] == 4 and row["per_payday"] == "3000.00"
    assert row["status"] == "saving" and row["wallet_name"] == "Savings"


def test_goals_sharing_a_wallet_fill_in_date_order(api, today, wallets):
    add(api, kind="income", amount="5000", date="2026-11-15", wallet=wallets["Savings"].pk)
    goal(api, wallets, name="Emergency", target="3000", target_date="2026-12-31")
    goal(api, wallets, name="Phone", target="10000", target_date="2027-06-30")
    rows = {r["name"]: r for r in api.get("/api/goals/").json()}
    assert rows["Emergency"]["saved"] == "3000.00" and rows["Emergency"]["status"] == "done"
    assert rows["Emergency"]["per_payday"] == "0.00"
    assert rows["Phone"]["saved"] == "2000.00"


def test_goal_validation_and_privacy(api, other_api, today, wallets):
    assert goal(api, wallets, target="0").status_code == 400
    assert goal(api, wallets, name=" ").status_code == 400
    gid = goal(api, wallets).json()["id"]
    assert other_api.get(f"/api/goals/{gid}/").status_code == 404
    assert other_api.delete(f"/api/goals/{gid}/").status_code == 404
    assert goal(other_api, wallets).status_code == 400  # someone else's wallet
    assert other_api.get("/api/goals/").json() == []


def test_cycle_report_compares_with_the_previous_cycle(api, today, wallets, categories):
    food, transport = categories["Food & drinks"].pk, categories["Transport"].pk
    gcash = wallets["GCash"].pk
    # Previous cycle: Oct 30 - Nov 14
    add(api, kind="income", amount="18000", date="2026-10-30", wallet=gcash)
    add(api, kind="expense", amount="3000", date="2026-11-02", wallet=gcash, category=food)
    add(api, kind="expense", amount="1000", date="2026-11-05", wallet=gcash, category=transport)
    # This cycle so far: Nov 15 - Nov 20
    add(api, kind="income", amount="18000", date="2026-11-15", wallet=gcash)
    add(api, kind="expense", amount="1200", date="2026-11-16", wallet=gcash, category=food)
    add(api, kind="expense", amount="600", date="2026-11-20", wallet=gcash, note="grab")
    report = api.get("/api/report/").json()
    assert report["start"] == "2026-11-15" and report["days"] == 6
    assert report["income"] == "18000.00" and report["spending"] == "1800.00"
    assert report["kept"] == "16200.00" and report["daily_average"] == "300.00"
    previous = report["previous"]
    assert previous["start"] == "2026-10-30" and previous["spending"] == "4000.00"
    cats = {c["name"]: c for c in report["categories"]}
    food_row = cats["Food & drinks"]
    assert food_row["total"] == "1200.00" and food_row["previous"] == "3000.00"
    assert cats["Transport"]["total"] == "0.00" and cats["Transport"]["previous"] == "1000.00"
    assert report["biggest"][0]["amount"] == "1200.00"


def test_report_ignores_neutral_moves(api, today, wallets):
    api.post(
        "/api/utang/",
        {
            "person": "P",
            "direction": "lent",
            "amount": "5000",
            "date": "2026-11-16",
            "wallet": wallets["GCash"].pk,
        },
        format="json",
    )
    report = api.get("/api/report/").json()
    assert report["spending"] == "0.00" and report["biggest"] == []
