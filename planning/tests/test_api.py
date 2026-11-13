"""Today summary, bills, schedule and the payday split over the API."""

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from planning.models import Bill, SplitRule

D = Decimal
pytestmark = pytest.mark.django_db


@pytest.fixture
def today(monkeypatch):
    """Freeze "today" at Fri 2026-11-20 (cycle Nov 15 -> Nov 30, kinsenas, no weekend shift)."""
    fixed = dt.date(2026, 11, 20)
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: fixed)
    return fixed


@pytest.fixture
def schedule(api):
    response = api.put(
        "/api/schedule/",
        {
            "frequency": "semi_monthly",
            "first_day": 15,
            "second_day": 30,
            "weekday": 4,
            "weekend_rule": "none",
            "expected_pay": "20000",
            "keep_aside": "500",
        },
        format="json",
    )
    assert response.status_code == 200
    return response.json()


def add(api, **data):
    return api.post("/api/transactions/", data, format="json").json()


def test_today_end_to_end(api, today, schedule, wallets, categories):
    # 10,500 in GCash, 2,000 in Savings (not spendable), a 3,000 bill due on the 25th.
    add(api, kind="income", amount="10500", date="2026-11-15", wallet=wallets["GCash"].pk)
    add(api, kind="income", amount="2000", date="2026-11-15", wallet=wallets["Savings"].pk)
    Bill.objects.create(
        owner=api.user, name="Rent", amount=D("3000"), due_day=25, wallet=wallets["GCash"]
    )
    add(
        api,
        kind="expense",
        amount="200",
        date="2026-11-20",
        wallet=wallets["GCash"].pk,
        category=categories["Food & drinks"].pk,
    )

    data = api.get("/api/today/").json()
    assert data["next_payday"] == "2026-11-30" and data["days_left"] == 10
    assert data["spendable"] == "10300.00"
    assert data["bills_reserved"] == "3000.00" and data["keep_aside"] == "500.00"
    # (10,300 - 3,000 - 500 + 200 spent today) / 10 days = 700/day, 500 left today.
    assert data["per_day"] == "700.00" and data["left_today"] == "500.00"
    assert data["status"] == "ok"
    assert data["bills"][0]["name"] == "Rent" and data["bills"][0]["paid"] is False
    assert data["recent"][0]["category_name"] == "Food & drinks"


def test_paying_a_bill_releases_its_reservation_and_is_not_todays_spending(
    api, today, schedule, wallets
):
    add(api, kind="income", amount="10000", date="2026-11-15", wallet=wallets["GCash"].pk)
    bill = Bill.objects.create(
        owner=api.user, name="Meralco", amount=D("2500"), due_day=25, wallet=wallets["GCash"]
    )
    before = api.get("/api/today/").json()
    response = api.post(f"/api/bills/{bill.pk}/pay/", {"due_date": "2026-11-25"}, format="json")
    assert response.status_code == 201 and response.json()["amount"] == "2500.00"
    after = api.get("/api/today/").json()
    assert after["bills_reserved"] == "0.00" and after["bills"][0]["paid"] is True
    assert after["per_day"] == before["per_day"] and after["left_today"] == before["left_today"]

    again = api.post(f"/api/bills/{bill.pk}/pay/", {"due_date": "2026-11-25"}, format="json")
    assert again.status_code == 400 and "already" in str(again.json())
    wrong = api.post(f"/api/bills/{bill.pk}/pay/", {"due_date": "2026-11-24"}, format="json")
    assert wrong.status_code == 400

    assert (
        api.post(
            f"/api/bills/{bill.pk}/unpay/", {"due_date": "2026-11-25"}, format="json"
        ).status_code
        == 204
    )
    assert api.get("/api/today/").json()["bills_reserved"] == "2500.00"


def test_payday_split(api, today, wallets, categories):
    SplitRule.objects.create(
        owner=api.user, name="Ipon", mode="percent", value=D("20"), to_wallet=wallets["Savings"]
    )
    SplitRule.objects.create(
        owner=api.user,
        name="Padala kay Nanay",
        mode="fixed",
        value=D("3000"),
        category=categories["Padala"],
    )
    preview = api.get("/api/payday/?amount=20000").json()
    assert [line["amount"] for line in preview["lines"]] == ["4000.00", "3000.00"]
    assert preview["remaining"] == "13000.00"

    response = api.post(
        "/api/payday/",
        {"amount": "20000", "wallet": wallets["Bank"].pk, "category": categories["Salary"].pk},
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["income"]["amount"] == "20000.00" and len(body["moves"]) == 2
    data = api.get("/api/today/").json()
    # Bank: 20,000 - 4,000 to savings - 3,000 padala. The padala is planned, not "spent today".
    assert data["spendable"] == "13000.00" and data["spent_today"] == "0.00"


def test_split_cannot_exceed_the_pay(api, today, wallets):
    SplitRule.objects.create(
        owner=api.user, name="Big", mode="fixed", value=D("9000"), to_wallet=wallets["Savings"]
    )
    response = api.post(
        "/api/payday/", {"amount": "5000", "wallet": wallets["Bank"].pk}, format="json"
    )
    assert response.status_code == 400 and "more than" in str(response.json())
    assert api.get("/api/payday/?amount=abc").status_code == 400
    assert api.get("/api/payday/?amount=NaN").status_code == 400


def test_schedule_validation(api):
    bad = api.put(
        "/api/schedule/",
        {"frequency": "semi_monthly", "first_day": 15, "second_day": 15},
        format="json",
    )
    assert bad.status_code == 400 and "second_day" in bad.json()
    assert api.put("/api/schedule/", {"first_day": 32}, format="json").status_code == 400


def test_split_rule_needs_exactly_one_target(api, wallets, categories):
    both = api.post(
        "/api/split-rules/",
        {
            "name": "x",
            "mode": "fixed",
            "value": "1",
            "to_wallet": wallets["Savings"].pk,
            "category": categories["Padala"].pk,
        },
        format="json",
    )
    assert both.status_code == 400
    over = api.post(
        "/api/split-rules/",
        {"name": "x", "mode": "percent", "value": "150", "to_wallet": wallets["Savings"].pk},
        format="json",
    )
    assert over.status_code == 400


def test_bills_are_private(api, other_api, wallets):
    bill = Bill.objects.create(
        owner=api.user, name="Rent", amount=D("1"), due_day=1, wallet=wallets["Cash"]
    )
    assert other_api.get(f"/api/bills/{bill.pk}/").status_code == 404
    pay = other_api.post(f"/api/bills/{bill.pk}/pay/", {"due_date": "2026-12-01"}, format="json")
    assert pay.status_code == 404
    mine = other_api.post(
        "/api/bills/",
        {"name": "Sneaky", "amount": "1", "due_day": 1, "wallet": wallets["Cash"].pk},
        format="json",
    )
    assert mine.status_code == 400
