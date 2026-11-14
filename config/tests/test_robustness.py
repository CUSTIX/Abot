"""Bad input must get a clear 4xx, never a server error (500)."""

import pytest

pytestmark = pytest.mark.django_db

JUNK = [
    {},
    {"amount": "abc", "date": "not-a-date", "wallet": "x"},
    {"amount": "1e309", "wallet": 999999},
    {"amount": "-5", "kind": "teleport", "due_day": 99, "members": 0},
    {"amount": None, "date": None, "wallet": None, "category": None},
    {"amount": "99999999999999.99"},
    {"amount": [1, 2], "name": {"a": 1}, "person": ["x"]},
    {"amount": "10", "date": "2026-02-30", "start_date": "0000-01-01"},
    {"name": "x" * 500, "note": "y" * 500, "person": "z" * 500},
]

CREATE = [
    "/api/wallets/",
    "/api/categories/",
    "/api/transactions/",
    "/api/bills/",
    "/api/split-rules/",
    "/api/payday/",
    "/api/utang/",
    "/api/paluwagan/",
]


@pytest.mark.parametrize("url", CREATE)
def test_create_endpoints_reject_junk_cleanly(api, url):
    for body in JUNK:
        response = api.post(url, body, format="json")
        assert response.status_code < 500, (url, body, response.status_code)


def test_actions_and_queries_reject_junk_cleanly(api, wallets):
    bill = api.post(
        "/api/bills/",
        {"name": "Rent", "amount": "100", "due_day": 5, "wallet": wallets["Cash"].pk},
        format="json",
    ).json()["id"]
    utang = api.post(
        "/api/utang/",
        {"person": "P", "direction": "lent", "amount": "10", "date": "2026-11-01"},
        format="json",
    ).json()["id"]
    for body in JUNK:
        for url in (
            f"/api/bills/{bill}/pay/",
            f"/api/bills/{bill}/unpay/",
            f"/api/utang/{utang}/pay/",
        ):
            assert api.post(url, body, format="json").status_code < 500, (url, body)
        assert api.put("/api/schedule/", body, format="json").status_code < 500, body
    for query in (
        "transactions/?start=2026-13-01",
        "transactions/?wallet=abc",
        "transactions/?category=-1",
        "spending/?start=2026-11-30&end=2026-11-01",
        "payday/?amount=Infinity",
        "payday/?amount=-1",
        "payday/?amount=1e20",
        "transactions/?page=999",
    ):
        assert api.get(f"/api/{query}").status_code < 500, query


def test_malformed_json_is_a_400(api):
    response = api.generic(
        "POST", "/api/transactions/", "{not json", content_type="application/json"
    )
    assert response.status_code == 400
