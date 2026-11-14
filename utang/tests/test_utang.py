"""Utang: lending/borrowing with partial payments, as neutral money moves."""

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
    fixed = dt.date(2026, 11, 20)  # cycle Nov 15 -> Nov 30 with the default schedule
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: fixed)
    return fixed


def fund(api, wallets, amount="5000"):
    api.post(
        "/api/transactions/",
        {"kind": "income", "amount": amount, "date": "2026-11-15", "wallet": wallets["GCash"].pk},
        format="json",
    )


def lend(api, wallets, **extra):
    body = {
        "person": "Pedro",
        "direction": "lent",
        "amount": "1000",
        "date": "2026-11-18",
        "wallet": wallets["GCash"].pk,
        **extra,
    }
    return api.post("/api/utang/", body, format="json")


def test_lending_moves_money_out_but_is_not_spending(api, today, wallets):
    fund(api, wallets)
    response = lend(api, wallets)
    assert response.status_code == 201
    assert response.json()["remaining"] == "1000.00"
    assert money.balances(api.user)[wallets["GCash"].pk] == D("4000")
    spending = api.get("/api/spending/?start=2026-11-01&end=2026-11-30").json()
    assert spending["total"] == "0"  # not spending
    txn = Transaction.objects.get(owner=api.user, source="utang")
    assert txn.neutral and txn.kind == "expense" and txn.note == "Lent to Pedro"


def test_partial_payments_until_settled(api, today, wallets):
    fund(api, wallets)
    utang_id = lend(api, wallets).json()["id"]
    pay = api.post(
        f"/api/utang/{utang_id}/pay/",
        {"amount": "400", "wallet": wallets["Cash"].pk},
        format="json",
    )
    assert pay.status_code == 201 and pay.json()["remaining"] == "600.00"
    too_much = api.post(f"/api/utang/{utang_id}/pay/", {"amount": "700"}, format="json")
    assert too_much.status_code == 400 and "600.00" in str(too_much.json())
    api.post(f"/api/utang/{utang_id}/pay/", {"amount": "600"}, format="json")  # no wallet: cash
    done = api.post(f"/api/utang/{utang_id}/pay/", {"amount": "1"}, format="json")
    assert done.status_code == 400 and "fully paid" in str(done.json())
    assert money.balances(api.user)[wallets["Cash"].pk] == D("400")
    assert api.get("/api/utang-summary/").json() == {"owed_to_me": "0.00", "i_owe": "0.00"}


def test_deleting_an_utang_puts_balances_back(api, today, wallets):
    fund(api, wallets)
    utang_id = lend(api, wallets).json()["id"]
    api.post(
        f"/api/utang/{utang_id}/pay/",
        {"amount": "250", "wallet": wallets["GCash"].pk},
        format="json",
    )
    assert api.delete(f"/api/utang/{utang_id}/").status_code == 204
    assert money.balances(api.user)[wallets["GCash"].pk] == D("5000")
    assert not Transaction.objects.filter(source="utang").exists()


def test_removing_one_payment(api, today, wallets):
    utang_id = lend(api, wallets, wallet=None).json()["id"]
    paid = api.post(f"/api/utang/{utang_id}/pay/", {"amount": "300"}, format="json").json()
    payment_id = paid["payments"][0]["id"]
    assert api.delete(f"/api/utang/{utang_id}/payments/{payment_id}/").status_code == 204
    assert api.get(f"/api/utang/{utang_id}/").json()["remaining"] == "1000.00"


def test_utang_moves_cannot_be_edited_as_plain_transactions(api, today, wallets):
    fund(api, wallets)
    lend(api, wallets)
    txn = Transaction.objects.get(source="utang")
    response = api.patch(f"/api/transactions/{txn.pk}/", {"amount": "1"}, format="json")
    assert response.status_code == 400 and "Utang" in str(response.json())
    assert api.delete(f"/api/transactions/{txn.pk}/").status_code == 400


def test_borrowed_utang_due_before_payday_is_set_aside(api, today, wallets):
    fund(api, wallets, "10000")
    before = api.get("/api/today/").json()
    api.post(
        "/api/utang/",
        {
            "person": "Ate Lyn",
            "direction": "borrowed",
            "amount": "2000",
            "date": "2026-11-19",
            "due_date": "2026-11-28",
            "wallet": wallets["GCash"].pk,
        },
        format="json",
    )
    after = api.get("/api/today/").json()
    # The borrowed 2,000 came in, but it all goes back before payday: nothing more to spend.
    assert D(after["spendable"]) - D(before["spendable"]) == D("2000")
    assert D(after["bills_reserved"]) - D(before["bills_reserved"]) == D("2000")
    assert after["per_day"] == before["per_day"]
    assert after["commitments"][0]["label"] == "Utang to Ate Lyn"


def test_validation(api, today, wallets):
    assert lend(api, wallets, person="  ").status_code == 400
    assert lend(api, wallets, amount="0").status_code == 400
    assert lend(api, wallets, due_date="2026-11-01").status_code == 400
    assert lend(api, wallets, direction="gift").status_code == 400


def test_utang_is_private(api, other_api, today, wallets):
    utang_id = lend(api, wallets).json()["id"]
    assert other_api.get(f"/api/utang/{utang_id}/").status_code == 404
    assert (
        other_api.post(f"/api/utang/{utang_id}/pay/", {"amount": "1"}, format="json").status_code
        == 404
    )
    assert other_api.delete(f"/api/utang/{utang_id}/").status_code == 404
    sneaky = other_api.post(
        "/api/utang/",
        {
            "person": "X",
            "direction": "lent",
            "amount": "1",
            "date": "2026-11-18",
            "wallet": wallets["GCash"].pk,
        },
        format="json",
    )
    assert sneaky.status_code == 400
