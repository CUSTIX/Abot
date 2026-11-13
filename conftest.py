"""Shared pytest fixtures."""

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from accounts import services as accounts

PASSWORD = "a-long-test-pass-9!"


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """The throttle cache lives in a database table (see settings.CACHES)."""
    with django_db_blocker.unblock():
        call_command("createcachetable")


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(username: str | None = None):
        counter["n"] += 1
        return accounts.sign_up(username=username or f"user{counter['n']}", password=PASSWORD)

    return _make


@pytest.fixture
def user(make_user):
    return make_user("juan")


@pytest.fixture
def api(user):
    """An API client signed in as `user`. CSRF is enforced (as in the browser) where it matters
    via `csrf_api` instead."""
    client = APIClient()
    client.force_login(user)
    client.user = user
    return client


@pytest.fixture
def other_api(make_user):
    client = APIClient()
    other = make_user("maria")
    client.force_login(other)
    client.user = other
    return client


@pytest.fixture
def wallets(user):
    from money.models import Wallet

    return {w.name: w for w in Wallet.objects.filter(owner=user)}


@pytest.fixture
def categories(user):
    from money.models import Category

    return {c.name: c for c in Category.objects.filter(owner=user)}
