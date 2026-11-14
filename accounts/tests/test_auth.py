"""Sign-up, login, CSRF and that every API URL needs a signed-in user."""

import re

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from conftest import PASSWORD

pytestmark = pytest.mark.django_db


def csrf_client():
    """A browser-like client: CSRF is enforced, so the token must be fetched first."""
    client = APIClient(enforce_csrf_checks=True)
    token = client.get("/api/auth/csrf/").json()["csrfToken"]
    client.credentials(HTTP_X_CSRFTOKEN=token)
    return client


def test_signup_logs_in_and_sets_up_wallets():
    client = csrf_client()
    response = client.post(
        "/api/auth/signup/", {"username": "ana", "password": PASSWORD}, format="json"
    )
    assert response.status_code == 201 and response.json()["username"] == "ana"
    assert len(client.get("/api/wallets/").json()) == 5


@pytest.mark.parametrize(
    "data,field",
    [
        ({"username": "ana", "password": "short"}, "password"),
        ({"username": "ana", "password": "password123"}, "password"),  # too common
        ({"username": "a b", "password": PASSWORD}, "username"),
    ],
)
def test_signup_validation(data, field):
    response = csrf_client().post("/api/auth/signup/", data, format="json")
    assert response.status_code == 400 and field in response.json()


def test_usernames_are_unique_ignoring_case(make_user):
    make_user("Juan")
    response = csrf_client().post(
        "/api/auth/signup/", {"username": "juan", "password": PASSWORD}, format="json"
    )
    assert response.status_code == 400 and "taken" in str(response.json())


def test_login_logout_and_me(make_user):
    make_user("pedro")
    client = csrf_client()
    bad = client.post("/api/auth/login/", {"username": "pedro", "password": "nope"}, format="json")
    assert bad.status_code == 400
    ok = client.post("/api/auth/login/", {"username": "pedro", "password": PASSWORD}, format="json")
    assert ok.status_code == 200
    # Login rotates the CSRF token; the app fetches a fresh one.
    client.credentials(HTTP_X_CSRFTOKEN=client.get("/api/auth/csrf/").json()["csrfToken"])
    assert client.get("/api/auth/me/").json()["user"]["username"] == "pedro"
    assert client.post("/api/auth/logout/").status_code == 204
    assert client.get("/api/auth/me/").json() == {"user": None}


def test_login_without_a_csrf_token_is_refused(make_user):
    make_user("pedro")
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(
        "/api/auth/login/", {"username": "pedro", "password": PASSWORD}, format="json"
    )
    assert response.status_code == 403


def test_writes_need_the_csrf_token_once_signed_in(user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    response = client.post("/api/wallets/", {"name": "Wallet X"}, format="json")
    assert response.status_code == 403


def test_login_is_throttled():
    client = csrf_client()
    codes = [
        client.post(
            "/api/auth/login/", {"username": "x", "password": "y"}, format="json"
        ).status_code
        for _ in range(11)
    ]
    assert codes[-1] == 429


def _api_urls(resolver=None, prefix=""):
    for p in (resolver or get_resolver()).url_patterns:
        if isinstance(p, URLResolver):
            yield from _api_urls(p, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern)


def test_every_api_url_needs_a_signed_in_user():
    public = {"api/auth/csrf/", "api/auth/signup/", "api/auth/login/", "api/auth/me/"}
    checked = 0
    for pattern in _api_urls():
        if not pattern.startswith("api/") or pattern in public:
            continue
        url = "/" + re.sub(r"\(\?P<\w+>[^)]*\)", "1", pattern).replace("^", "").replace("$", "")
        response = APIClient().get(url)
        assert response.status_code in (401, 403, 405), (url, response.status_code)
        checked += 1
    assert checked >= 10
