"""Wallets, categories and transactions over the API, including isolation between users."""

import datetime as dt
from decimal import Decimal

import pytest

from money import selectors
from money.models import Transaction

D = Decimal
pytestmark = pytest.mark.django_db
TODAY = dt.date(2026, 11, 20)


def add(api, **data):
    return api.post("/api/transactions/", {"date": TODAY.isoformat(), **data}, format="json")


def test_signup_gives_starter_wallets_and_categories(api, wallets, categories):
    assert {"Cash", "GCash", "Maya", "Bank", "Savings"} <= set(wallets)
    assert wallets["Savings"].spendable is False
    assert categories["Food & drinks"].keywords.startswith("kape")
    names = [w["name"] for w in api.get("/api/wallets/").json()]
    assert names[:2] == ["Cash", "GCash"]


def test_balances_follow_the_ledger(api, wallets, categories):
    gcash, cash = wallets["GCash"], wallets["Cash"]
    add(api, kind="income", amount="5000", wallet=gcash.pk, category=categories["Salary"].pk)
    add(
        api,
        kind="expense",
        amount="150.50",
        wallet=gcash.pk,
        category=categories["Food & drinks"].pk,
    )
    add(api, kind="transfer", amount="1000", wallet=gcash.pk, to_wallet=cash.pk)
    balances = selectors.balances(api.user)
    assert balances[gcash.pk] == D("3849.50") and balances[cash.pk] == D("1000")
    rows = {w["name"]: w["balance"] for w in api.get("/api/wallets/").json()}
    assert rows["GCash"] == "3849.50" and rows["Cash"] == "1000.00"


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"kind": "transfer", "amount": "10"}, "to_wallet"),
        ({"kind": "expense", "amount": "0"}, "amount"),
        ({"kind": "expense", "amount": "-5"}, "amount"),
        ({"kind": "expense", "amount": "10", "category": "Salary"}, "category"),
    ],
)
def test_transaction_rules(api, wallets, categories, payload, field):
    if "category" in payload:
        payload["category"] = categories[payload["category"]].pk
    response = add(api, wallet=wallets["Cash"].pk, **payload)
    assert response.status_code == 400 and field in response.json()


def test_transfer_to_the_same_wallet_is_refused(api, wallets):
    response = add(
        api, kind="transfer", amount="5", wallet=wallets["Cash"].pk, to_wallet=wallets["Cash"].pk
    )
    assert response.status_code == 400


def test_switching_a_transfer_to_an_expense_drops_the_destination(api, wallets, categories):
    txn = add(
        api, kind="transfer", amount="5", wallet=wallets["Cash"].pk, to_wallet=wallets["GCash"].pk
    ).json()
    response = api.patch(
        f"/api/transactions/{txn['id']}/",
        {"kind": "expense", "category": categories["Fun"].pk},
        format="json",
    )
    assert response.status_code == 200 and response.json()["to_wallet"] is None


def test_filters_and_search(api, wallets, categories):
    add(
        api,
        kind="expense",
        amount="80",
        wallet=wallets["Cash"].pk,
        note="jeep to work",
        category=categories["Transport"].pk,
    )
    add(api, kind="expense", amount="120", wallet=wallets["GCash"].pk, note="kape")
    rows = api.get("/api/transactions/?q=jeep").json()["results"]
    assert [r["note"] for r in rows] == ["jeep to work"]
    assert api.get(f"/api/transactions/?wallet={wallets['GCash'].pk}").json()["count"] == 1
    assert api.get("/api/transactions/?start=2026-11-21").json()["count"] == 0
    assert api.get("/api/transactions/?start=yesterday").status_code == 400
    assert api.get("/api/transactions/?kind=refund").status_code == 400


def test_a_used_wallet_is_archived_not_deleted(api, wallets):
    add(api, kind="expense", amount="5", wallet=wallets["Maya"].pk)
    assert api.delete(f"/api/wallets/{wallets['Maya'].pk}/").json() == {"archived": True}
    assert "Maya" not in [w["name"] for w in api.get("/api/wallets/").json()]
    assert api.delete(f"/api/wallets/{wallets['Bank'].pk}/").status_code == 204
    response = add(api, kind="expense", amount="5", wallet=wallets["Maya"].pk)
    assert response.status_code == 400 and "archived" in str(response.json())


def test_duplicate_wallet_names_are_refused(api):
    response = api.post("/api/wallets/", {"name": "gcash", "kind": "ewallet"}, format="json")
    assert response.status_code == 400 and "already" in response.json()["name"][0]


def test_spending_by_category(api, wallets, categories):
    add(
        api,
        kind="expense",
        amount="100",
        wallet=wallets["Cash"].pk,
        category=categories["Food & drinks"].pk,
    )
    add(
        api,
        kind="expense",
        amount="300",
        wallet=wallets["Cash"].pk,
        category=categories["Transport"].pk,
    )
    data = api.get("/api/spending/?start=2026-11-01&end=2026-11-30").json()
    assert data["total"] == "400.00"
    assert [c["name"] for c in data["categories"]] == ["Transport", "Food & drinks"]


# ---- isolation between users -------------------------------------------------------------------


def test_another_users_rows_are_invisible(api, other_api, wallets):
    txn = add(api, kind="expense", amount="99", wallet=wallets["Cash"].pk).json()
    wallet_id = wallets["Cash"].pk
    for url in (f"/api/transactions/{txn['id']}/", f"/api/wallets/{wallet_id}/"):
        assert other_api.get(url).status_code == 404
        assert other_api.patch(url, {"note": "x"}, format="json").status_code == 404
        assert other_api.delete(url).status_code == 404
    assert other_api.get("/api/transactions/").json()["count"] == 0
    assert Transaction.objects.filter(pk=txn["id"]).exists()


def test_cannot_book_into_someone_elses_wallet_or_category(api, other_api, wallets, categories):
    response = other_api.post(
        "/api/transactions/",
        {"kind": "expense", "amount": "1", "date": "2026-11-20", "wallet": wallets["Cash"].pk},
        format="json",
    )
    assert response.status_code == 400 and "does not exist" in str(response.json()["wallet"])
    mine = other_api.get("/api/wallets/").json()[0]["id"]
    response = other_api.post(
        "/api/transactions/",
        {
            "kind": "expense",
            "amount": "1",
            "date": "2026-11-20",
            "wallet": mine,
            "category": categories["Fun"].pk,
        },
        format="json",
    )
    assert response.status_code == 400 and "category" in response.json()


def test_a_wallet_a_bill_still_uses_is_archived_not_a_server_error(api, wallets):
    from planning.models import Bill

    Bill.objects.create(owner=api.user, name="Rent", amount="1", due_day=1, wallet=wallets["Bank"])
    response = api.delete(f"/api/wallets/{wallets['Bank'].pk}/")
    assert response.status_code == 200 and response.json() == {"archived": True}


def test_deleting_a_wallet_keeps_split_rules_that_use_it(api, wallets):
    from planning.models import SplitRule

    rule = SplitRule.objects.create(
        owner=api.user, name="Ipon", mode="percent", value="10", to_wallet=wallets["Savings"]
    )
    assert api.delete(f"/api/wallets/{wallets['Savings'].pk}/").json() == {"archived": True}
    assert SplitRule.objects.filter(pk=rule.pk).exists()


def test_quick_add_learns_the_words_you_file(api, wallets, categories):
    food = categories["Food & drinks"]
    add(
        api,
        kind="expense",
        amount="45",
        wallet=wallets["Cash"].pk,
        category=food.pk,
        note="siomai sa kanto",
    )
    food.refresh_from_db()
    assert food.keywords.endswith(", siomai")
    # Known words, numbers and words another category owns are not learned again.
    cash = wallets["Cash"].pk
    for note in ("siomai", "jeep", "7"):
        add(api, kind="expense", amount="45", wallet=cash, category=food.pk, note=note)
    food.refresh_from_db()
    assert food.keywords.count("siomai") == 1 and "jeep" not in food.keywords


def test_csv_export_is_mine_only_and_spreadsheet_safe(api, other_api, wallets, categories):
    add(
        api,
        kind="expense",
        amount="99.5",
        wallet=wallets["GCash"].pk,
        category=categories["Fun"].pk,
        note='=HYPERLINK("http://evil","click")',
    )
    add(api, kind="transfer", amount="10", wallet=wallets["Cash"].pk, to_wallet=wallets["Maya"].pk)
    response = api.get("/api/export.csv")
    assert response.status_code == 200 and response["Content-Type"].startswith("text/csv")
    text = response.content.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0] == "date,type,amount,wallet,to_wallet,category,note,neutral"
    assert len(lines) == 3
    assert "'=HYPERLINK" in text and ",=HYPERLINK" not in text
    assert "99.50" in text and "Cash,Maya" in text
    other = other_api.get("/api/export.csv").content.decode("utf-8-sig").strip().splitlines()
    assert other == [lines[0]]
    assert api.get("/api/export.csv?start=2026-12-01").content.decode("utf-8-sig").count("\n") == 1
